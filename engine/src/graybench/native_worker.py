"""Standalone standard-library worker run inside the pinned Qiskit image.

The host passes one JSON payload on stdin and a new result-file path as argv[1].
Candidate stdout is untrusted; only a result written after test completion counts.
This is native same-process reproduction, not a defense against deliberate test tampering.
"""

import json
import os
import sys

MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_RESULT_BYTES = 16 * 1024


def _candidate_frame(exc: BaseException) -> bool:
    trace = exc.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_filename == "<candidate>":
            return True
        trace = trace.tb_next
    return False


def _failure(status: str, phase: str, exc: BaseException) -> dict:
    return {
        "status": status,
        "phase": phase,
        "exception_type": type(exc).__name__,
        "detail": str(exc)[:1024],
        "completed": True,
    }


def run_payload(payload: dict) -> dict:
    """Execute answer and pinned test in one namespace with native object identity."""
    # Keep worker primitives in local slots before untrusted code can rebind builtins.
    compile_source, execute_source, is_callable = compile, exec, callable
    if payload.get("protocol") != "qhe-native-worker-v1":
        raise ValueError("Unknown native worker protocol")
    if payload.get("suite") not in {"normal", "hard"}:
        raise ValueError("Unknown native suite")
    exception_policy = payload.get("exception_policy", "conservative_unattributed_v1")
    if exception_policy not in {
        "conservative_unattributed_v1",
        "test_exception_is_failure_v1",
    }:
        raise ValueError("Unknown native exception policy")
    for key in ("entry_point", "code", "public_prefix", "test"):
        if not isinstance(payload.get(key), str):
            raise ValueError("Malformed native payload field: " + key)
    namespace = {"__name__": "native_candidate"}
    if payload["public_prefix"]:
        try:
            execute_source(
                compile_source(payload["public_prefix"], "<public-prefix>", "exec"), namespace
            )
        except BaseException as exc:
            return _failure("infrastructure_error", "public_prefix", exc)
    try:
        execute_source(compile_source(payload["code"], "<candidate>", "exec"), namespace)
    except BaseException as exc:
        return _failure("candidate_error", "candidate", exc)
    candidate = namespace.get(payload["entry_point"])
    if not is_callable(candidate):
        return {
            "status": "candidate_error",
            "phase": "entry_point",
            "exception_type": "MissingCallable",
            "detail": "Declared entry point is not callable",
            "completed": True,
        }
    try:
        execute_source(compile_source(payload["test"], "<pinned-test>", "exec"), namespace)
        if payload["suite"] == "normal":
            namespace["check"](candidate)
    except BaseException as exc:
        status = (
            "candidate_error"
            if _candidate_frame(exc)
            else "fail"
            if isinstance(exc, AssertionError) or exception_policy == "test_exception_is_failure_v1"
            else "infrastructure_error"
        )
        return _failure(status, "test", exc)
    return {"status": "pass", "phase": "test", "completed": True}


def main() -> int:
    # Keep the result writer outside straightforward candidate rebinding of modules.
    serialize = json.dumps
    open_result, write_result, sync_result, close_result = (
        os.open,
        os.write,
        os.fsync,
        os.close,
    )
    if len(sys.argv) != 2:
        return 2
    result_path = sys.argv[1]
    raw = sys.stdin.buffer.read(MAX_PAYLOAD_BYTES + 1)
    if len(raw) > MAX_PAYLOAD_BYTES:
        return 2
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 2
        result = run_payload(payload)
        encoded = serialize(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_RESULT_BYTES:
            return 2
        fd = open_result(result_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            write_result(fd, encoded)
            sync_result(fd)
        finally:
            close_result(fd)
    except (OSError, ValueError, TypeError):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

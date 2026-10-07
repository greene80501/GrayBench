"""Host-owned isolation and strict parsing for candidate-submitted JSON values.

No response from this module is a verdict. The trusted semantic oracle is a
separate process and may only conclude pass/fail from declared value semantics.
"""

import hashlib
import json
import math
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from graybench.extraction import extract
from graybench.identity import canonical, identity
from graybench.judgment_evidence import completion_binding
from graybench.protected_value_contract import (
    ProtectedValueContract,
    ValueCall,
    validate_value,
)

WORKER = Path(__file__).with_name("protected_value_worker.py")
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
READY_MARKER = b"graybench-protected-value-worker-ready-v1\n"


class TrustedCaseError(ValueError):
    """The frozen judge supplied an invalid call; it is not a candidate mistake."""


@dataclass(frozen=True)
class ValueExecution:
    outcome: str
    values: tuple[object, ...]
    evidence: dict


def value_payload(
    contract: ProtectedValueContract, completion: str, calls: tuple[ValueCall, ...]
) -> dict:
    """Candidate receives public code and inputs, never expected outputs or tests."""
    try:
        if not calls:
            raise ValueError("Protected value evaluation requires at least one call")
        wire_calls = []
        for call in calls:
            if len(call.args) != len(contract.positional) or set(call.kwargs) != set(
                contract.keywords
            ):
                raise ValueError("Call does not match declared argument names and count")
            for value, shape in zip(call.args, contract.positional, strict=True):
                validate_value(value, shape)
            for name, value in call.kwargs.items():
                name.encode("utf-8")
                validate_value(value, contract.keywords[name])
            wire_calls.append(call.model_dump(mode="json"))
    except Exception as exc:
        raise TrustedCaseError("Invalid frozen protected call") from exc
    extracted = extract(completion, contract.public, contract.extraction)
    if extracted.error:
        raise ValueError("Candidate answer does not match frozen extraction policy")
    return {
        "protocol": "protected-value-v1",
        "entry_point": contract.public.entry_point,
        "code": extracted.public_prefix + extracted.code,
        "calls": wire_calls,
    }


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant: " + value)


def parse_value_response(
    wire: bytes, contract: ProtectedValueContract, *, expected_count: int
) -> tuple[object, ...]:
    if len(wire) > 8 * 1024 * 1024:
        raise ValueError("Candidate value response exceeds byte limit")
    response = json.loads(
        wire.decode("utf-8", errors="strict"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    if (
        type(response) is not dict
        or set(response) != {"protocol", "completed", "values"}
        or response["protocol"] != "protected-value-v1"
        or response["completed"] is not True
        or type(response["values"]) is not list
        or len(response["values"]) != expected_count
    ):
        raise ValueError("Candidate did not submit the declared number of values")
    for value in response["values"]:
        validate_value(value, contract.result)
    return tuple(response["values"])


def value_command(
    *,
    docker: str,
    image: str,
    source_dir: Path,
    memory_bytes: int,
    cpus: float,
    pids_limit: int,
    tmpfs_bytes: int,
    name: str,
) -> list[str]:
    return [
        docker,
        "run",
        "-i",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(pids_limit),
        "--memory",
        str(memory_bytes),
        "--memory-swap",
        str(memory_bytes),
        "--cpus",
        str(cpus),
        "--user",
        "65534:65534",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,mode=1777,size={tmpfs_bytes}",
        "--mount",
        f"type=bind,source={source_dir.resolve()},target=/worker,readonly",
        "--workdir",
        "/tmp",
        "--env",
        "HOME=/tmp",
        "--env",
        "OMP_NUM_THREADS=1",
        image,
        "python",
        "-u",
        "/worker/protected_value_worker.py",
    ]


class ValueRunner:
    def __init__(
        self,
        *,
        image: str,
        docker: str = "docker",
        timeout: float = 120.0,
        output_limit: int = 1024 * 1024,
        memory_bytes: int = 2 * 1024**3,
        cpus: float = 2.0,
        pids_limit: int = 64,
        tmpfs_bytes: int = 64 * 1024**2,
    ):
        if (
            re.fullmatch(r"sha256:[0-9a-f]{64}", image) is None
            or not math.isfinite(timeout)
            or timeout <= 0
            or type(output_limit) is not int
            or not 1024 <= output_limit <= 16 * 1024**2
            or type(memory_bytes) is not int
            or memory_bytes < 128 * 1024**2
            or not math.isfinite(cpus)
            or cpus <= 0
            or type(pids_limit) is not int
            or pids_limit < 2
            or type(tmpfs_bytes) is not int
            or tmpfs_bytes < 1024**2
        ):
            raise ValueError("Invalid protected value runtime identity")
        self.image, self.docker, self.timeout, self.output_limit = (
            image,
            docker,
            timeout,
            output_limit,
        )
        self.memory_bytes, self.cpus, self.pids_limit = memory_bytes, cpus, pids_limit
        self.tmpfs_bytes = tmpfs_bytes

    def manifest(self, contract: ProtectedValueContract) -> dict:
        return {
            "track": contract.track,
            "contract_digest": contract.digest,
            "worker_sha256": hashlib.sha256(WORKER.read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "image": self.image,
            "timeout_seconds": self.timeout,
            "output_limit": self.output_limit,
            "payload_limit": MAX_PAYLOAD_BYTES,
            "memory_bytes": self.memory_bytes,
            "cpus": self.cpus,
            "pids_limit": self.pids_limit,
            "tmpfs_bytes": self.tmpfs_bytes,
            "origin_claim": "candidate_submitted_value_only",
            "release_eligible": False,
        }

    def execute(
        self, contract: ProtectedValueContract, completion: str, calls: tuple[ValueCall, ...]
    ) -> ValueExecution:
        manifest = self.manifest(contract)
        evidence = {
            "manifest": manifest,
            "origin_claim": "candidate_submitted_value_only",
            **completion_binding(completion),
        }
        try:
            payload = value_payload(contract, completion, calls)
            wire = canonical(payload)
        except TrustedCaseError:
            return ValueExecution(
                "infrastructure_error", (), {**evidence, "reason": "invalid_frozen_case"}
            )
        except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
            return ValueExecution("candidate_error", (), {**evidence, "reason": type(exc).__name__})
        if len(wire) > MAX_PAYLOAD_BYTES:
            return ValueExecution("candidate_error", (), {**evidence, "reason": "payload_limit"})
        evidence["payload_sha256"] = hashlib.sha256(wire).hexdigest()
        return self._execute(contract, wire, len(calls), evidence)

    def _execute(
        self, contract: ProtectedValueContract, wire: bytes, count: int, evidence: dict
    ) -> ValueExecution:
        name = "graybench-protected-value-" + uuid.uuid4().hex
        output = [bytearray(), bytearray()]
        total = [0]
        lock = threading.Lock()
        exceeded = threading.Event()
        process = None
        readers = []
        writer = None
        timed_out = False
        with tempfile.TemporaryDirectory(prefix="graybench-protected-value-") as directory:
            source_dir = Path(directory) / "worker"
            source_dir.mkdir()
            shutil.copyfile(WORKER, source_dir / "protected_value_worker.py")
            command = value_command(
                docker=self.docker,
                image=self.image,
                source_dir=source_dir,
                memory_bytes=self.memory_bytes,
                cpus=self.cpus,
                pids_limit=self.pids_limit,
                tmpfs_bytes=self.tmpfs_bytes,
                name=name,
            )

            def drain(stream, buffer):
                try:
                    while chunk := stream.read(8192):
                        with lock:
                            remaining = max(0, self.output_limit - total[0])
                            buffer.extend(chunk[:remaining])
                            total[0] += min(len(chunk), remaining)
                            overflow = len(chunk) > remaining
                        if overflow:
                            exceeded.set()
                            process.kill()
                            return
                finally:
                    stream.close()

            def send():
                try:
                    process.stdin.write(wire)
                    process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    process.stdin.close()

            try:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                readers = [
                    threading.Thread(target=drain, args=(stream, buffer), daemon=True)
                    for stream, buffer in zip((process.stdout, process.stderr), output, strict=True)
                ]
                for reader in readers:
                    reader.start()
                writer = threading.Thread(target=send, daemon=True)
                writer.start()
                process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            except OSError as exc:
                return ValueExecution(
                    "infrastructure_error", (), {**evidence, "reason": type(exc).__name__}
                )
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                if writer is not None:
                    writer.join(timeout=2)
                for reader in readers:
                    reader.join(timeout=2)
                try:
                    subprocess.run(
                        [self.docker, "rm", "--force", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass
        evidence = {
            **evidence,
            "exit_code": process.returncode,
            "stdout_sha256": hashlib.sha256(output[0]).hexdigest(),
            "stderr_sha256": hashlib.sha256(output[1]).hexdigest(),
            "stderr_excerpt": output[1][:4096].decode("utf-8", errors="replace"),
            "output_bytes": total[0],
            "worker_started": READY_MARKER in output[1],
            "manifest_digest": identity(evidence["manifest"]),
        }
        if timed_out:
            return ValueExecution("timeout", (), {**evidence, "reason": "candidate_timeout"})
        if exceeded.is_set():
            return ValueExecution("candidate_error", (), {**evidence, "reason": "output_limit"})
        if process.returncode != 0:
            return ValueExecution(
                "candidate_error" if evidence["worker_started"] else "infrastructure_error",
                (),
                {
                    **evidence,
                    "reason": "candidate_nonzero_exit"
                    if evidence["worker_started"]
                    else "container_nonzero_before_worker",
                },
            )
        try:
            values = parse_value_response(bytes(output[0]), contract, expected_count=count)
        except (ValueError, UnicodeError, RecursionError) as exc:
            return ValueExecution("candidate_error", (), {**evidence, "reason": type(exc).__name__})
        return ValueExecution("returned", values, evidence)

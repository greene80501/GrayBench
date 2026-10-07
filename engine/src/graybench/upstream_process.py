"""Trusted upstream-test process with a data-only proxy into a separate candidate container."""

import ast
import contextlib
import json
import sys
from pathlib import Path

from circuit_wire import WireError, WireLimitError
from value_wire import decode, encode


class BridgeFailure(Exception):
    def __init__(self, outcome, detail):
        self.outcome, self.detail = outcome, detail


def main():
    task = json.loads(Path("/judge/task.json").read_text(encoding="utf-8"))
    channel = sys.stdout
    calls = 0

    def proxy(*args, **kwargs):
        nonlocal calls
        calls += 1
        try:
            before_args, before_kwargs = encode(args), encode(kwargs)
        except (WireError, TypeError) as exc:
            raise BridgeFailure("unsupported", str(exc)) from exc
        print(
            json.dumps(
                {"kind": "call", "sequence": calls, "args": before_args, "kwargs": before_kwargs},
                allow_nan=False,
            ),
            file=channel,
            flush=True,
        )
        line = sys.stdin.readline(1024 * 1024 + 1)
        if not line or len(line) > 1024 * 1024:
            raise BridgeFailure("infrastructure_error", "Missing or oversized bridge response")
        response = json.loads(line)
        if response["sequence"] != calls:
            raise BridgeFailure("infrastructure_error", "Unmatched bridge response")
        if response["outcome"] != "returned":
            raise BridgeFailure(response["outcome"], response.get("detail", "candidate failure"))
        wire = response["response"]
        if wire["args_after"] != before_args or wire["kwargs_after"] != before_kwargs:
            raise BridgeFailure(
                "unsupported", "Alias-aware input mutation bridge is not implemented"
            )
        try:
            return decode(wire["value"])
        except WireLimitError as exc:
            raise BridgeFailure("unsupported", str(exc)) from exc
        except (WireError, ValueError, TypeError) as exc:
            raise BridgeFailure("candidate_error", str(exc)) from exc

    evidence = {}
    try:
        tree = ast.parse(task["test"])
        checks = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "check"]
        if len(checks) != 1 or not any(isinstance(n, ast.Assert) for n in ast.walk(checks[0])):
            raise BridgeFailure("infrastructure_error", "Expected one check with assertions")
        tree.body = [
            n
            for n in tree.body
            if not (
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Name)
                and n.value.func.id == "check"
            )
        ]
        namespace = {"__name__": "trusted_tests", task["entry_point"]: proxy}
        with contextlib.redirect_stdout(sys.stderr):
            exec(compile(task["prefix"], "public_prefix.py", "exec"), namespace)
            exec(compile(tree, "upstream_tests.py", "exec"), namespace)
            namespace["check"](proxy)
        outcome = "pass"
    except BridgeFailure as exc:
        outcome, evidence = exc.outcome, {"detail": exc.detail}
    except AssertionError as exc:
        outcome, evidence = "fail", {"detail": str(exc)[:4096]}
    except Exception as exc:
        # A non-assertion test error can be a bad candidate value or an oracle/environment defect.
        # Preserve it as unresolved rather than silently penalizing a model.
        outcome, evidence = (
            "infrastructure_error",
            {"exception": type(exc).__name__, "detail": str(exc)[:4096]},
        )
    print(
        json.dumps(
            {"kind": "judgment", "outcome": outcome, "evidence": {**evidence, "calls": calls}},
            allow_nan=False,
        ),
        file=channel,
        flush=True,
    )


if __name__ == "__main__":
    main()

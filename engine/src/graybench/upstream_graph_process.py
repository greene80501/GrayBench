"""Trusted upstream-test process with a data-only proxy into a separate candidate container."""

import ast
import contextlib
import json
import sys
from pathlib import Path

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_owned import GraphReconstructionError
from graybench.graph_rpc import EXCEPTIONS, validate_arguments, validate_root_shapes, validate_roots
from graybench.graph_wire import GraphArena, GraphLimits


class BridgeFailure(BaseException):
    def __init__(self, outcome, detail):
        self.outcome, self.detail = outcome, detail


def main():
    task = json.loads(Path("/judge/task.json").read_text(encoding="utf-8"))
    channel = sys.stdout
    calls = 0
    registry = PublicAnchorRegistry.capture()
    arena = GraphArena(
        side="judge",
        session=task["graph_session"],
        limits=GraphLimits.from_record(task["graph_limits"]),
        anchors=registry,
    )
    remote_exceptions = []
    bridge_failure = None

    def exchange(*args, **kwargs):
        nonlocal calls
        calls += 1
        try:
            outgoing = arena.snapshot({"args": args, "kwargs": kwargs}, sequence=calls)
        except GraphReconstructionError as exc:
            raise BridgeFailure("infrastructure_error", str(exc)) from exc
        except WireError as exc:
            raise BridgeFailure("unsupported", str(exc)) from exc
        print(
            json.dumps({"kind": "call", "sequence": calls, "graph": outgoing}, allow_nan=False),
            file=channel,
            flush=True,
        )
        line = sys.stdin.readline(arena.limits.message_bytes + 1)
        if not line or len(line) > arena.limits.message_bytes:
            raise BridgeFailure("infrastructure_error", "Missing or oversized bridge response")
        response = json.loads(line)
        if type(response.get("sequence")) is not int or response["sequence"] != calls:
            raise BridgeFailure("infrastructure_error", "Unmatched bridge response")
        if response["outcome"] != "returned":
            raise BridgeFailure(response["outcome"], response.get("detail", "candidate failure"))
        wire = response["response"]
        try:
            from graybench.circuit_wire import fields

            fields(wire, {"protocol", "sequence", "graph", "exception"})
            if (
                type(wire["protocol"]) is not int
                or wire["protocol"] != 4
                or type(wire["sequence"]) is not int
                or wire["sequence"] != calls
            ):
                raise WireError("Unmatched graph response")
            raised = wire["exception"]
            if raised is not None and (type(raised) is not str or raised not in EXCEPTIONS):
                raise WireError("Unknown value exception")
            validate_roots(wire["graph"], {"args", "kwargs", "result", "exception_args"})
            # Argument container identity is part of the call contract, not only
            # equality of independently serialized argument values.
            for key in ("args", "kwargs"):
                if wire["graph"]["roots"][key] != outgoing["roots"][key]:
                    raise WireError("Candidate replaced an argument root")
            prepared = arena.prepare(wire["graph"], sequence=calls)
            validate_root_shapes(wire["graph"], response=True, raised=raised)
            roots = arena.commit(prepared)
            validate_arguments(roots)
            if raised is None:
                if roots["exception_args"] is not None:
                    raise WireError("Unexpected exception arguments")
                return roots["result"]
            if type(roots["exception_args"]) is not tuple or roots["result"] is not None:
                raise WireError("Invalid exception result roots")
            exc = EXCEPTIONS[raised](*roots["exception_args"])
        except GraphReconstructionError as exc:
            raise BridgeFailure("infrastructure_error", str(exc)) from exc
        except WireLimitError as exc:
            raise BridgeFailure("unsupported", str(exc)) from exc
        except WireError as exc:
            raise BridgeFailure("candidate_error", str(exc)) from exc
        remote_exceptions.append(exc)
        raise exc

    def proxy(*args, **kwargs):
        nonlocal bridge_failure
        if bridge_failure is not None:
            raise bridge_failure
        try:
            return exchange(*args, **kwargs)
        except BridgeFailure as exc:
            bridge_failure = exc
            raise
        except BaseException as exc:
            if any(exc is item for item in remote_exceptions):
                raise
            # Record failure before touching its diagnostic: even __str__ may
            # fail. Only explicitly reconstructed candidate exceptions may be
            # consumed by test code without making this attempt unresolved.
            bridge_failure = BridgeFailure(
                "infrastructure_error", "Unexpected trusted bridge failure"
            )
            try:
                bridge_failure.detail += f": {type(exc).__name__}: {exc}"[:4096]
            except BaseException:
                pass
            raise bridge_failure from exc

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
            "candidate_error"
            if any(exc is item for item in remote_exceptions)
            else "infrastructure_error",
            {"exception": type(exc).__name__, "detail": str(exc)[:4096]},
        )
    # Tests may catch BaseException. Transport/infrastructure diagnostics must
    # still block judgment; they are never candidate value-exceptions.
    if bridge_failure is not None:
        outcome = bridge_failure.outcome
        evidence = {"detail": bridge_failure.detail}
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

"""Untrusted protocol4 worker; emits state, never a verdict."""

import contextlib
import json
import sys
from pathlib import Path

from graybench.circuit_wire import WireError, fields
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_rpc import (
    exception_name,
    validate_arguments,
    validate_root_shapes,
    validate_roots,
)
from graybench.graph_wire import GraphArena, GraphLimits


def main():
    channel = sys.stdout
    config = json.loads(Path("/input/graph_config.json").read_text())
    registry = PublicAnchorRegistry.capture()
    registry.validate_manifest(config["anchors"])
    arena = GraphArena(
        side="candidate",
        session=config["session"],
        limits=GraphLimits.from_record(config["limits"]),
        anchors=registry,
    )
    namespace = {"__name__": "candidate"}
    with contextlib.redirect_stdout(sys.stderr):
        prefix = Path("/input/public_prefix.py")
        if prefix.exists():
            exec(compile(prefix.read_text(encoding="utf-8"), "public_prefix.py", "exec"), namespace)
    print(
        json.dumps({"protocol": 4, "runtime_ready": True, "anchors": registry.manifest()}),
        file=channel,
        flush=True,
    )
    if json.loads(sys.stdin.readline()) != {"protocol": 4, "start": True}:
        raise ValueError("Missing candidate start authorization")
    with contextlib.redirect_stdout(sys.stderr):
        source = Path("/input/candidate.py").read_text(encoding="utf-8")
        exec(compile(source, "candidate.py", "exec"), namespace)
    print(json.dumps({"protocol": 4, "ready": True}), file=channel, flush=True)
    sequence = 0
    for line in sys.stdin:
        phase = "decoding"
        request = json.loads(line)
        try:
            fields(
                request,
                {"protocol", "session", "sequence", "entry_point", "graph", "discard_result"},
            )
            sequence += 1
            if (
                type(request["sequence"]) is not int
                or request["sequence"] != sequence
                or type(request["protocol"]) is not int
                or request["protocol"] != 4
                or request["session"] != config["session"]
                or type(request["entry_point"]) is not str
                or type(request["discard_result"]) is not bool
            ):
                raise WireError("Invalid graph call request")
            validate_roots(request["graph"], {"args", "kwargs"})
            with contextlib.redirect_stdout(sys.stderr):
                prepared = arena.prepare(request["graph"], sequence=sequence)
                validate_root_shapes(request["graph"])
                roots = arena.commit(prepared)
                validate_arguments(roots)
                phase = "execution"
                result, raised, raised_args = None, None, None
                try:
                    result = namespace[request["entry_point"]](*roots["args"], **roots["kwargs"])
                    if request["discard_result"]:
                        result = None
                except BaseException as exc:
                    phase = "encoding"
                    raised = exception_name(exc)
                    raised_args = exc.args
                phase = "encoding"
                outgoing = arena.snapshot(
                    {**roots, "result": result, "exception_args": raised_args}, sequence=sequence
                )
            response = {"protocol": 4, "sequence": sequence, "graph": outgoing, "exception": raised}
        except BaseException as exc:
            response = {
                "protocol": 4,
                "sequence": request.get("sequence"),
                "error": type(exc).__name__,
                "phase": phase,
                "detail": str(exc)[:4096],
            }
        print(json.dumps(response, allow_nan=False), file=channel, flush=True)


if __name__ == "__main__":
    main()

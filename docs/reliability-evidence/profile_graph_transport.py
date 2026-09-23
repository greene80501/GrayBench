"""Local source-bound transport comparison; not protected timing or model scoring."""

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter

from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_delta import DeltaGraphArena
from graybench.graph_wire import GraphArena, GraphLimits, wire_bytes
from graybench.provenance import source_manifest

parser = argparse.ArgumentParser()
parser.add_argument("mode", choices=("snapshot-v1", "delta-v1"))
parser.add_argument("output", type=Path)
args = parser.parse_args()
if args.output.exists():
    raise FileExistsError(args.output)
source = source_manifest()
registry = PublicAnchorRegistry.capture()
arenas = [
    GraphArena(side=side, session="profile-transport", anchors=registry,
               limits=GraphLimits(message_bytes=16777216))
    for side in ("judge", "candidate")
]
if args.mode == "delta-v1":
    arenas = [DeltaGraphArena(arena, wire_limit=16777216) for arena in arenas]
judge, candidate = arenas
rows = []


def timed(call):
    started = time.perf_counter()
    value = call()
    return value, time.perf_counter() - started


started = time.perf_counter()
for sequence in range(1, 101):
    forward, t1 = timed(lambda: judge.snapshot({"args": (), "kwargs": {}}, sequence=sequence))
    prepared, t2 = timed(lambda: candidate.prepare(forward, sequence=sequence))
    roots, t3 = timed(lambda: candidate.commit(prepared))
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.rz(Parameter("th"), 0)
    backward, t4 = timed(lambda: candidate.snapshot(
        {**roots, "result": qc, "exception_args": None}, sequence=sequence))
    prepared, t5 = timed(lambda: judge.prepare(backward, sequence=sequence))
    result, t6 = timed(lambda: judge.commit(prepared))
    result["result"].assign_parameters([0.5], inplace=True)
    rows.append({
        "call": sequence,
        "forward_bytes": len(wire_bytes(forward)),
        "backward_bytes": len(wire_bytes(backward)),
        "forward_records": len(forward["nodes"]),
        "backward_records": len(backward["nodes"]),
        "seconds": dict(zip(("judge_snapshot", "candidate_prepare", "candidate_commit",
                              "candidate_snapshot", "judge_prepare", "judge_commit"),
                             (t1, t2, t3, t4, t5, t6), strict=True)),
    })
elapsed = time.perf_counter() - started
assert source_manifest() == source
result = {
    "purpose": __doc__, "mode": args.mode, "source": source,
    "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "python": platform.python_version(), "qiskit": qiskit.__version__,
    "wire_limit": 16777216, "state_limit": 16777216,
    "calls": 100, "elapsed_seconds": elapsed,
    "total_graph_bytes": sum(row["forward_bytes"] + row["backward_bytes"] for row in rows),
    "stage_seconds": {key: sum(row["seconds"][key] for row in rows) for key in rows[0]["seconds"]},
    "rows": rows,
    "limitations": [
        "Two local arenas share a process and public-anchor registry; no Docker, pipe or envelopes.",
        "Single wall-clock observation per mode; unrelated machine load is not controlled.",
        "All exported objects remain retained and full graph validation/reconstruction still runs.",
    ],
}
with args.output.open("x", encoding="utf-8") as stream:
    json.dump(result, stream, indent=2)
print(json.dumps({key: value for key, value in result.items() if key not in ("rows", "source")}))

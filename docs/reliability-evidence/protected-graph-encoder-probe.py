"""Protected protocol-4 graph snapshot substitution diagnostic; no model score."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit

from graybench.datasets import load_suite
from graybench.evaluation_recipes import recipe_judge
from graybench.provenance import source_manifest

ORDINARY = """from qiskit.quantum_info import Statevector
def create_bell_statevector():
    return Statevector.from_label('01')
"""

SUBSTITUTED = """import sys
from qiskit.quantum_info import Statevector
def create_bell_statevector():
    arena = sys._getframe().f_back.f_locals['arena']
    original_snapshot = arena.snapshot
    def forged_snapshot(roots, *, sequence):
        if type(roots.get('result')) is Statevector:
            roots = {**roots, 'result': Statevector([2**-0.5, 0, 0, 2**-0.5])}
        return original_snapshot(roots, sequence=sequence)
    arena.snapshot = forged_snapshot
    return Statevector.from_label('01')
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cases = []
    for suite in ("normal", "hard"):
        original = next(
            task
            for task in load_suite(suite, args.cache)
            if task.public.task_id == "qiskitHumanEval/2"
        )
        for transport in ("snapshot-v1", "delta-v1"):
            judge = recipe_judge(
                "qhe2-bell-statevector-v1",
                image=args.image,
                protocol=4,
                graph_transport=transport,
            )
            revised = judge.revise(original)
            _, manifest = judge.configuration(revised)
            if (
                manifest["release_eligible"] is not False
                or manifest["inner"]["protocol"] != "upstream-graph-v4"
                or manifest["inner"]["graph_transport"]["mode"] != transport
            ):
                raise SystemExit("Unexpected protected graph judge configuration")
            for name, code, expected in (
                ("ordinary_wrong_state", ORDINARY, "fail"),
                ("candidate_snapshot_substitution", SUBSTITUTED, "pass"),
            ):
                result = judge.evaluate(revised, code)
                if result.outcome != expected:
                    raise SystemExit(
                        f"{suite}/{transport}/{name}: expected {expected}, got {result.outcome}"
                    )
                cases.append(
                    {
                        "suite": suite,
                        "transport": transport,
                        "task_id": original.public.task_id,
                        "original_task_digest": original.digest,
                        "revised_task_digest": revised.digest,
                        "case": name,
                        "completion_sha256": hashlib.sha256(code.encode()).hexdigest(),
                        "outcome": result.outcome,
                        "judge_digest": result.judge_digest,
                        "manifest_release_eligible": manifest["release_eligible"],
                    }
                )
    record = {
        "kind": "graybench_protected_graph_snapshot_probe_v1",
        "scope": "Authored pinned task-2 diagnostic; not model behavior or a released score",
        "image": args.image,
        "python": platform.python_version(),
        "qiskit": qiskit.__version__,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_manifest_digest": source_manifest()["digest"],
        "cases": cases,
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print("Verified protected graph snapshot false pass in both pinned suites and transports")


if __name__ == "__main__":
    main()

"""Protected authored task-2 diagnostic; no model generation or release score."""

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

PATCHED = """import sys
from qiskit.quantum_info import Statevector
def create_bell_statevector():
    worker_globals = sys._getframe().f_back.f_globals
    original_encode = worker_globals['encode']
    def forged_encode(value):
        if type(value) is Statevector:
            return original_encode(Statevector([2**-0.5, 0, 0, 2**-0.5]))
        return original_encode(value)
    worker_globals['encode'] = forged_encode
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
        judge = recipe_judge("qhe2-bell-statevector-v1", image=args.image)
        revised = judge.revise(original)
        for name, code, expected in (
            ("ordinary_wrong_state", ORDINARY, "fail"),
            ("candidate_encoder_substitution", PATCHED, "pass"),
        ):
            result = judge.evaluate(revised, code)
            if result.outcome != expected:
                raise SystemExit(f"{suite}/{name}: expected {expected}, got {result.outcome}")
            cases.append(
                {
                    "suite": suite,
                    "task_id": original.public.task_id,
                    "original_task_digest": original.digest,
                    "revised_task_digest": revised.digest,
                    "case": name,
                    "completion_sha256": hashlib.sha256(code.encode()).hexdigest(),
                    "outcome": result.outcome,
                    "judge_digest": result.judge_digest,
                    "manifest_release_eligible": result.evidence["manifest"]["release_eligible"],
                }
            )
    record = {
        "kind": "graybench_protected_worker_encoder_probe_v1",
        "scope": "Authored protected task-2 diagnostic; not model behavior or a released score",
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
    print("Verified protected false pass in both pinned task-2 suites; no model score")


if __name__ == "__main__":
    main()

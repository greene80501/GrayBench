"""Pinned density-matrix oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from graybench.upstream import UpstreamJudge
from qiskit.quantum_info import DensityMatrix, entanglement_of_formation, mutual_information

BELL = "[[0.5,0,0,0.5],[0,0,0,0],[0,0,0,0],[0.5,0,0,0.5]]"
BOUNDARY = "[[0.5,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0.5]]"
MIXED = "[[0.25,0,0,0],[0,0.25,0,0],[0,0,0.25,0],[0,0,0,0.25]]"
CASES = {
    137: {
        "bell_ten": (BELL, 10, "pass"),
        "bell_three": (BELL, 3, "fail"),
    },
    138: {
        "bell_ten": (BELL, 10, "pass"),
        "bell_three": (BELL, 3, "fail"),
        "boundary_ten": (BOUNDARY, 10, "pass"),
        "mixed_ten": (MIXED, 10, "fail"),
    },
}


def completion(task, matrix, count):
    body = (
        "\n    from qiskit.quantum_info import DensityMatrix\n"
        f"    return [DensityMatrix({matrix})] * {count}\n"
    )
    if task.public.suite == "normal":
        return body
    return f"def {task.public.entry_point}(epsilon):" + body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    judge = UpstreamJudge(image=args.image)
    observations = []
    for suite in ("normal", "hard"):
        tasks = {t.public.task_id: t for t in load_suite(suite, args.cache)}
        for number, cases in CASES.items():
            task = tasks[f"qiskitHumanEval/{number}"]
            for name, (matrix, count, expected) in cases.items():
                code = completion(task, matrix, count)
                result = judge.evaluate(task, code)
                if result.outcome != expected:
                    raise RuntimeError(f"Unexpected {suite}/{number}/{name}: {result.outcome}")
                observations.append(
                    {
                        "suite": suite,
                        "task_digest": task.digest,
                        "case": name,
                        "completion_sha256": hashlib.sha256(code.encode()).hexdigest(),
                        "outcome": result.outcome,
                        "judge_digest": result.judge_digest,
                    }
                )
    bell = DensityMatrix(json.loads(BELL))
    boundary = DensityMatrix(json.loads(BOUNDARY))
    witness = {
        "bell_entanglement_of_formation": float(entanglement_of_formation(bell)),
        "bell_mutual_information": float(mutual_information(bell)),
        "boundary_mutual_information": float(mutual_information(boundary)),
        "boundary_test_tolerance": 1.0,
    }
    if not (witness["bell_entanglement_of_formation"] > 0.1):
        raise RuntimeError("Bell entanglement witness no longer qualifies")
    if not (witness["bell_mutual_information"] > 1.0):
        raise RuntimeError("Bell mutual-information witness no longer qualifies")
    if witness["boundary_mutual_information"] != witness["boundary_test_tolerance"]:
        raise RuntimeError("Mutual-information boundary witness changed")
    print(
        json.dumps(
            {
                "kind": "graybench_task137_138_oracle_probe_v1",
                "scope": "Pinned protected-bridge diagnostic, not a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
                "witness": witness,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

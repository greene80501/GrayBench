"""Pinned task-144 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from graybench.upstream import UpstreamJudge

BODY = {
    "pure_product": "return [DensityMatrix.from_label('00') for _ in range(10)]",
    "varied_product": (
        "return [DensityMatrix.from_label(label) "
        "for label in (['00', '01', '10', '11', '00'] * 2)]"
    ),
    "wrong_length": "return [DensityMatrix.from_label('00') for _ in range(9)]",
    "wrong_type": "return [[1, 0, 0, 0] for _ in range(10)]",
    "entangled": (
        "return [DensityMatrix([[.5, 0, 0, .5], [0, 0, 0, 0], "
        "[0, 0, 0, 0], [.5, 0, 0, .5]]) for _ in range(10)]"
    ),
}
EXPECTED = {
    "reference": "pass",
    "pure_product": "pass",
    "varied_product": "pass",
    "wrong_length": "fail",
    "wrong_type": "fail",
    "entangled": "fail",
}


def variants(task):
    if task.public.suite == "normal":
        return {"reference": task.canonical_solution} | {
            name: f"\n    {body}\n" for name, body in BODY.items()
        }
    prefix = "from qiskit.quantum_info import DensityMatrix\ndef concurrence_dataset():\n"
    return {"reference": task.canonical_solution} | {
        name: prefix + f"    {body}\n" for name, body in BODY.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    judge = UpstreamJudge(image=args.image)
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/144"
        )
        for name, completion in variants(task).items():
            result = judge.evaluate(task, completion)
            if result.outcome != EXPECTED[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {result.outcome}")
            observations.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "completion_sha256": hashlib.sha256(completion.encode()).hexdigest(),
                    "outcome": result.outcome,
                    "judge_digest": result.judge_digest,
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task144_oracle_probe_v1",
                "scope": "Pinned protected-bridge diagnostic, not a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

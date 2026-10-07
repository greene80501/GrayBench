"""Pinned task-136 tolerance diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from graybench.upstream import UpstreamJudge
from qiskit.quantum_info import DensityMatrix, entropy

BODY = {
    "pure_control": "return [DensityMatrix.from_label('0') for _ in range(10)]",
    "fixed_near_pure": (
        "return [DensityMatrix([[.9996, 0], [0, .0004]]) for _ in range(10)]"
    ),
    "mixed_control": "return [DensityMatrix([[.9, 0], [0, .1]]) for _ in range(10)]",
    "short_control": "return [DensityMatrix.from_label('0') for _ in range(9)]",
}
EXPECTED = {
    "reference": "pass",
    "pure_control": "pass",
    "fixed_near_pure": "pass",
    "mixed_control": "fail",
    "short_control": "fail",
}


def variants(task):
    if task.public.suite == "normal":
        return {"reference": task.canonical_solution} | {
            name: f"\n    {body}\n" for name, body in BODY.items()
        }
    prefix = "from qiskit.quantum_info import DensityMatrix\ndef pure_states(ε):\n"
    return {"reference": task.canonical_solution} | {
        name: prefix + f"    {body}\n" for name, body in BODY.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    witness_entropy = float(entropy(DensityMatrix([[0.9996, 0], [0, 0.0004]])))
    if not 0.001 < witness_entropy < 0.01:
        raise RuntimeError("Fixed-state tolerance witness is no longer discriminating")
    judge = UpstreamJudge(image=args.image)
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/136"
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
                "kind": "graybench_task136_oracle_probe_v1",
                "scope": "Pinned protected-bridge diagnostic, not a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
                "counterexample": {
                    "candidate": "fixed_near_pure",
                    "state_entropy": witness_entropy,
                    "pinned_test_epsilon": 0.01,
                    "valid_unchecked_epsilon": 0.001,
                    "fails_valid_unchecked_epsilon": witness_entropy >= 0.001,
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

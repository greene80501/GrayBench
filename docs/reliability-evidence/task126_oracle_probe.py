"""Pinned task-126 fidelity diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from graybench.upstream import UpstreamJudge


def variants(task):
    if task.public.suite == "normal":
        return {
            "reference": task.canonical_solution,
            "constant_one": "\n    return 1.0\n",
            "constant_zero_control": "\n    return 0.0\n",
        }
    prefix = "def calculate_phase_difference_fidelity():\n"
    return {
        "reference": task.canonical_solution,
        "constant_one": prefix + "    return 1.0\n",
        "constant_zero_control": prefix + "    return 0.0\n",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {"reference": "pass", "constant_one": "pass", "constant_zero_control": "fail"}
    judge = UpstreamJudge(image=args.image)
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/126"
        )
        for name, code in variants(task).items():
            result = judge.evaluate(task, code)
            if result.outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {result.outcome}")
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
    print(
        json.dumps(
            {
                "kind": "graybench_task126_fidelity_probe_v1",
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

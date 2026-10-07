"""Pinned task-149 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from graybench.upstream import UpstreamJudge
from qiskit.primitives import BitArray


def variants(task):
    if task.public.suite == "normal":
        return {
            "reference": task.canonical_solution,
            "first_string": "\n    return bits.get_bitstrings()[0]\n",
            "last_string_control": "\n    return bits.get_bitstrings()[-1]\n",
        }
    prefix = "from qiskit.primitives import BitArray\ndef most_common_result(bits):\n"
    return {
        "reference": task.canonical_solution,
        "first_string": prefix + "    return bits.get_bitstrings()[0]\n",
        "last_string_control": prefix + "    return bits.get_bitstrings()[-1]\n",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {"reference": "pass", "first_string": "pass", "last_string_control": "fail"}
    judge = UpstreamJudge(image=args.image)
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/149"
        )
        for name, completion in variants(task).items():
            result = judge.evaluate(task, completion)
            if result.outcome != expected[name]:
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
    counts = {"101": 3, "001": 50}
    strings = BitArray.from_counts(counts).get_bitstrings()
    witness = {
        "counts": counts,
        "first_string": strings[0],
        "majority_string": max(counts, key=counts.get),
    }
    if witness["first_string"] == witness["majority_string"]:
        raise RuntimeError("Reversed-order witness no longer distinguishes candidates")
    print(
        json.dumps(
            {
                "kind": "graybench_task149_oracle_probe_v1",
                "scope": "Pinned protected-bridge diagnostic, not a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
                "counterexample": witness,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

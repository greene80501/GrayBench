"""Pinned task-145 zero-width diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from graybench.upstream import UpstreamJudge


def variants(task):
    bad_zero_body = (
        "\n    if n == 0:\n"
        "        return QuantumCircuit(1)\n"
        "    return QFT(num_qubits=n, approximation_degree=0, inverse=True)\n"
    )
    identity_body = "\n    return QuantumCircuit(n)\n"
    if task.public.suite == "normal":
        return {
            "reference": task.canonical_solution,
            "one_qubit_for_zero": bad_zero_body,
            "identity_control": identity_body,
        }
    prefix = (
        "from qiskit.circuit.library import QFT\n"
        "from qiskit import QuantumCircuit\n"
        "def qft_inverse(n):"
    )
    return {
        "reference": task.canonical_solution,
        "one_qubit_for_zero": prefix + bad_zero_body,
        "identity_control": prefix + identity_body,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {"reference": "pass", "one_qubit_for_zero": "pass", "identity_control": "fail"}
    judge = UpstreamJudge(image=args.image)
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/145"
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
    hard_task = next(
        t for t in load_suite("hard", args.cache) if t.public.task_id == "qiskitHumanEval/145"
    )
    authored = {}
    exec(variants(hard_task)["one_qubit_for_zero"], authored)
    returned_qubits = authored["qft_inverse"](0).num_qubits
    if returned_qubits != 1:
        raise RuntimeError("Zero-width counterexample no longer returns one qubit")
    print(
        json.dumps(
            {
                "kind": "graybench_task145_zero_width_probe_v1",
                "scope": "Pinned protected-bridge diagnostic, not a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
                "counterexample": {
                    "requested_qubits": 0,
                    "returned_qubits": returned_qubits,
                    "test_assertion_caught_by": "except Exception",
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

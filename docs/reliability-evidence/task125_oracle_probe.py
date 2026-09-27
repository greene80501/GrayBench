"""Exact pinned task-125 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator


def authored_body(*, first_width=3, second_gate="z"):
    return (
        "    from qiskit import QuantumCircuit\n"
        "    from qiskit.circuit import Gate\n"
        "    from qiskit.converters import circuit_to_gate\n"
        "    if circ.num_qubits == 3:\n"
        f"        return Gate('unrelated', {first_width}, [])\n"
        "    other = QuantumCircuit(1)\n"
        f"    other.{second_gate}(0)\n"
        "    return circuit_to_gate(other)\n"
    )


def cases(task):
    variants = {
        "reference": task.canonical_solution,
        "independent_to_gate": "    return circ.to_gate()\n",
        "fixed_shape_wrong_action": authored_body(),
        "wrong_first_width_control": authored_body(first_width=2),
        "wrong_second_operator_control": authored_body(second_gate="x"),
    }
    for name, implementation in variants.items():
        if name == "reference":
            source = (
                task.public.prompt + implementation
                if task.public.suite == "normal"
                else implementation
            )
        elif task.public.suite == "normal":
            source = task.public.prompt + "\n" + implementation
        else:
            source = "def circ_to_gate(circ):\n" + implementation
        yield name, source


def first_input():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.cx(0, 1)
    return circuit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "independent_to_gate": "pass",
        "fixed_shape_wrong_action": "pass",
        "wrong_first_width_control": "fail",
        "wrong_second_operator_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/125"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-125-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-125-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["circ_to_gate"])
                outcome, assertion = "pass", None
            except AssertionError as exc:
                outcome, assertion = "fail", str(exc)
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}; assertion={assertion}")
            returned = namespace["circ_to_gate"](first_input())
            correct_action = None
            try:
                correct_action = Operator(returned).equiv(Operator(first_input()))
            except Exception:
                correct_action = False
            if name in {"fixed_shape_wrong_action", "wrong_second_operator_control"}:
                if correct_action is not False or returned.num_qubits != 3:
                    raise RuntimeError(
                        "Authored wrong-action fixture was not constructed as intended"
                    )
            observations.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "assertion": assertion,
                    "first_gate_type": type(returned).__name__,
                    "first_gate_width": returned.num_qubits,
                    "first_action_matches_input": correct_action,
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task125_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

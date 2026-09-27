"""Exact pinned task-128 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite


def authored_body(*, prepare=True, correction="x"):
    preparation = "    for index in range(3):\n        circuit.h(q[index])\n" if prepare else ""
    return (
        "    from qiskit.circuit import QuantumCircuit, QuantumRegister, ClassicalRegister\n"
        "    from qiskit.circuit.classical import expr\n"
        "    q = QuantumRegister(4, 'q')\n"
        "    c = ClassicalRegister(4, 'c')\n"
        "    circuit = QuantumCircuit(q, c)\n"
        + preparation
        + "    circuit.measure(q[:3], c[:3])\n"
        "    condition = expr.bit_xor(expr.bit_xor(c[0], c[1]), c[2])\n"
        "    with circuit.if_test(condition):\n"
        f"        circuit.{correction}(q[3])\n"
        "    circuit.measure(q[3], c[3])\n"
        "    return circuit\n"
    )


def cases(task):
    variants = {
        "reference": task.canonical_solution,
        "independent_explicit_h": authored_body(),
        "no_h_preparation": authored_body(prepare=False),
        "wrong_conditional_action_control": authored_body(correction="z"),
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
            source = "def conditional_quantum_circuit():\n" + implementation
        yield name, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "independent_explicit_h": "pass",
        "no_h_preparation": "pass",
        "wrong_conditional_action_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/128"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-128-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-128-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["conditional_quantum_circuit"])
                outcome, assertion = "pass", None
            except AssertionError as exc:
                outcome, assertion = "fail", str(exc)
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}; assertion={assertion}")
            circuit = namespace["conditional_quantum_circuit"]()
            first_three_h = sum(
                instruction.operation.name == "h"
                and circuit.find_bit(instruction.qubits[0]).index < 3
                for instruction in circuit.data
                if instruction.qubits
            )
            if name == "no_h_preparation" and first_three_h != 0:
                raise RuntimeError("Authored no-H fixture was not constructed as intended")
            observations.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "assertion": assertion,
                    "first_three_h_count": first_three_h,
                    "measurement_count": circuit.count_ops().get("measure", 0),
                    "if_else_count": circuit.count_ops().get("if_else", 0),
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task128_exact_oracle_probe_v1",
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

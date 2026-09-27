"""Exact pinned task-117 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import qiskit
from graybench.datasets import PINS, load_suite
from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate
from qiskit.exceptions import QiskitError
from qiskit.quantum_info import Operator
from qiskit.synthesis import TwoQubitBasisDecomposer

MUTANTS = {
    "constant_cx": "qc = QuantumCircuit(2)\nqc.cx(0, 1)\nreturn qc",
    "nonunitary_measurement": (
        "qc = QuantumCircuit(2, 1)\nqc.cx(0, 1)\nqc.measure(0, 0)\nreturn qc"
    ),
    "no_cx_control": "qc = QuantumCircuit(2)\nqc.x(0)\nreturn qc",
    "wrong_width_control": "qc = QuantumCircuit(3)\nqc.cx(0, 1)\nreturn qc",
}
EXPECTED = {
    "reference": "pass",
    "constant_cx": "pass",
    "nonunitary_measurement": "pass",
    "no_cx_control": "fail",
    "wrong_width_control": "fail",
}


def candidate(task, name):
    if name == "reference":
        solution = task.canonical_solution
    elif task.public.suite == "normal":
        solution = "\n" + "\n".join("    " + line for line in MUTANTS[name].splitlines()) + "\n"
    else:
        solution = (
            "from qiskit import QuantumCircuit\n"
            "def decompose_unitary(unitary):\n"
            + "\n".join("    " + line for line in MUTANTS[name].splitlines())
            + "\n"
        )
    return task.public.prompt + solution if task.public.suite == "normal" else solution


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    cases = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/117"
        )
        for name in EXPECTED:
            source = candidate(task, name)
            namespace = {}
            try:
                exec(compile(source, "<authored-task-117-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-117-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["decompose_unitary"])
                outcome, assertion = "pass", None
            except AssertionError as exc:
                outcome, assertion = "fail", str(exc)
            if outcome != EXPECTED[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}")
            cases.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "assertion": assertion,
                }
            )
    identity = Operator(np.eye(4))
    fixed = QuantumCircuit(2)
    fixed.cx(0, 1)
    assert not Operator(fixed).equiv(identity)
    measured = QuantumCircuit(2, 1)
    measured.cx(0, 1)
    measured.measure(0, 0)
    try:
        Operator(measured)
    except QiskitError:
        measured_operator = "QiskitError"
    else:
        raise RuntimeError("Measured circuit unexpectedly has a unitary operator")
    canonical_identity = TwoQubitBasisDecomposer(CXGate())(identity)
    assert Operator(canonical_identity).equiv(identity)
    canonical_identity_cx = sum(inst.operation.name == "cx" for inst in canonical_identity.data)
    assert canonical_identity_cx == 0
    print(
        json.dumps(
            {
                "kind": "graybench_task117_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "semantic_controls": {
                    "fixed_cx_equiv_identity_input": False,
                    "measured_circuit_operator": measured_operator,
                    "canonical_identity_decomposition_cx_count": canonical_identity_cx,
                },
                "cases": cases,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

"""Trusted authored exact-test task-111 diagnostic; never a model score."""

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np
import qiskit
from graybench.datasets import PINS, load_suite
from qiskit.quantum_info import Statevector

AUTHORED = {
    "valid_ry_rz": (
        "    qc = QuantumCircuit(1)\n"
        "    theta = Parameter('theta')\n"
        "    phi = Parameter('phi')\n"
        "    qc.ry(theta, 0)\n"
        "    qc.rz(phi, 0)\n"
        "    return qc\n"
    ),
    "rz_only": (
        "    qc = QuantumCircuit(1)\n"
        "    a = Parameter('a')\n"
        "    b = Parameter('b')\n"
        "    qc.rz(a, 0)\n"
        "    qc.rz(b, 0)\n"
        "    return qc\n"
    ),
    "two_qubits": (
        "    qc = QuantumCircuit(2)\n"
        "    a = Parameter('a')\n"
        "    b = Parameter('b')\n"
        "    qc.ry(a, 0)\n"
        "    qc.rz(b, 1)\n"
        "    return qc\n"
    ),
    "one_parameter_control": (
        "    qc = QuantumCircuit(1)\n"
        "    a = Parameter('a')\n"
        "    qc.ry(a, 0)\n"
        "    return qc\n"
    ),
}
EXPECTED_OUTCOME = {
    "reference": "pass",
    "valid_ry_rz": "pass",
    "rz_only": "pass",
    "two_qubits": "pass",
    "one_parameter_control": "fail",
}
GRID = tuple(
    (a, b) for a in (0.0, math.pi / 2, math.pi) for b in (0.0, math.pi / 2, math.pi)
)


def sources(task):
    for name, body in {"reference": task.canonical_solution, **AUTHORED}.items():
        if name == "reference":
            source = task.public.prompt + body if task.public.suite == "normal" else body
        elif task.public.suite == "normal":
            source = task.public.prompt + "\n" + body
        else:
            source = (
                "from qiskit.circuit import QuantumCircuit, Parameter\n"
                "def circuit():\n"
                + body
            )
        yield name, source


def witness(candidate):
    circuit = candidate()
    parameters = sorted(circuit.parameters, key=lambda p: p.name)
    states = []
    excited_populations = []
    for values in GRID:
        mapping = dict(zip(parameters, values, strict=False))
        state = Statevector.from_instruction(circuit.assign_parameters(mapping)).data
        density = np.outer(state, state.conj())
        if circuit.num_qubits == 1:
            excited_populations.append(float(abs(state[1]) ** 2))
        if not any(np.allclose(density, prior) for prior in states):
            states.append(density)
    return {
        "qubits": circuit.num_qubits,
        "parameters": circuit.num_parameters,
        "distinct_physical_states_on_grid": len(states),
        "max_excited_population_on_grid": (
            max(excited_populations) if excited_populations else None
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    cases = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/111"
        )
        for name, source in sources(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-111-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-111-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace[task.public.entry_point])
                outcome = "pass"
            except AssertionError:
                outcome = "fail"
            if outcome != EXPECTED_OUTCOME[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}")
            observed = witness(namespace[task.public.entry_point])
            if name in {"reference", "valid_ry_rz"} and not (
                observed["qubits"] == 1 and observed["distinct_physical_states_on_grid"] > 1
                and observed["max_excited_population_on_grid"] > 0.99
            ):
                raise RuntimeError(f"Invalid positive {suite}/{name}: {observed}")
            if name == "rz_only" and not (
                observed["qubits"] == 1 and observed["distinct_physical_states_on_grid"] == 1
                and observed["max_excited_population_on_grid"] < 1e-9
            ):
                raise RuntimeError(f"Invalid RZ-only witness {suite}: {observed}")
            if name == "two_qubits" and observed["qubits"] != 2:
                raise RuntimeError(f"Invalid width witness {suite}: {observed}")
            cases.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "pinned_test_outcome": outcome,
                    "witness": observed,
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task111_native_oracle_probe_v1",
                "scope": "Authored exact pinned-test diagnostic, not a model score",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "parameter_grid": GRID,
                "cases": cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

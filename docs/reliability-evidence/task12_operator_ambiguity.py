"""Pinned task-12 diagnostic using only fixed authored circuits on the host.

Bell state preparation does not uniquely determine the full unitary. This
diagnostic is not sandbox qualification, task admission, or model execution.
"""

import argparse
import ast
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from graybench.datasets import PINS, load_suite
from graybench.identity import canonical
from graybench.provenance import source_manifest

SOURCE_DIGESTS = (
    "7a42452895eaa8f638e9e73236893e6c869d28892546158d7f4db0113472b5b5",
    "5700f4524e774918b4c85ca328e5352c05d5e644a5375dfd7652e81823d3bd08",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cx(control, target):
    matrix = np.zeros((4, 4), dtype=complex)
    for column in range(4):
        row = column ^ (1 << target) if column & (1 << control) else column
        matrix[row, column] = 1
    return matrix


def fixtures():
    h = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
    z = np.diag([1, -1])
    reference = cx(0, 1) @ np.kron(np.eye(2), h)
    definitions = (
        ("reference_order", [("h", [0]), ("cx", [0, 1])], 0.0, reference),
        (
            "mirrored_preparation",
            [("h", [1]), ("cx", [1, 0])],
            0.0,
            cx(1, 0) @ np.kron(h, np.eye(2)),
        ),
        (
            "preparation_with_initial_z",
            [("z", [1]), ("h", [0]), ("cx", [0, 1])],
            0.0,
            reference @ np.kron(z, np.eye(2)),
        ),
        ("global_phase_reference", [("h", [0]), ("cx", [0, 1])], 0.37, np.exp(0.37j) * reference),
        ("identity_wrong_state", [], 0.0, np.eye(4, dtype=complex)),
    )
    for name, operations, phase, matrix in definitions:
        circuit = QuantumCircuit(2)
        for gate, wires in operations:
            getattr(circuit, gate)(*wires)
        circuit.global_phase = phase
        yield name, operations, phase, matrix, Operator(circuit).data


def probe(normal, hard):
    if (normal.digest, hard.digest) != SOURCE_DIGESTS:
        raise ValueError("Diagnostic requires exact pinned task 12")
    checks = []
    for task in (normal, hard):
        matches = [
            node
            for node in ast.parse(task.upstream_test).body
            if isinstance(node, ast.FunctionDef) and node.name == "check"
        ]
        if len(matches) != 1:
            raise ValueError("Pinned check shape changed")
        namespace = {"QuantumCircuit": QuantumCircuit, "Operator": Operator}
        exec(
            compile(ast.Module(body=matches, type_ignores=[]), "pinned-task12-check", "exec"),
            namespace,
        )
        checks.append(namespace["check"])
    bell = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    rows = []
    for name, operations, phase, matrix, sdk_matrix in fixtures():
        outcomes = []
        for check in checks:
            try:
                check(lambda sdk_matrix=sdk_matrix: sdk_matrix)
            except AssertionError:
                outcomes.append("fail")
            else:
                outcomes.append("pass")
        column = matrix[:, 0]
        overlap = np.vdot(bell, column)
        aligned = column * np.exp(-1j * np.angle(overlap))
        state_error = float(np.max(np.abs(aligned - bell)))
        sdk_error = float(np.max(np.abs(matrix - sdk_matrix)))
        unitary_error = float(np.max(np.abs(matrix.conj().T @ matrix - np.eye(4))))
        if sdk_error >= 1e-14 or unitary_error >= 1e-14:
            raise ValueError("Authored fixture failed independent matrix calibration")
        rows.append(
            {
                "id": name,
                "operations": [[gate, wires] for gate, wires in operations],
                "global_phase": phase,
                "matrix": [
                    [[float(value.real), float(value.imag)] for value in row] for row in matrix
                ],
                "judged_matrix": [
                    [[float(value.real), float(value.imag)] for value in row] for row in sdk_matrix
                ],
                "sdk_matrix_error": sdk_error,
                "unitary_error": unitary_error,
                "bell_state_error_up_to_global_phase": state_error,
                "bell_preparation": state_error < 1e-14,
                "normal": outcomes[0],
                "hard": outcomes[1],
            }
        )
    return rows


def build(cache):
    tasks = [
        next(t for t in load_suite(s, cache) if t.public.task_id == "qiskitHumanEval/12")
        for s in ("normal", "hard")
    ]
    return {
        "kind": "graybench_task12_operator_ambiguity_v1",
        "scope": "fixed authored host values against pinned checks; no sandbox qualification",
        "publication_eligible": False,
        "independent_review": False,
        "dataset_pins": PINS,
        "source_task_digests": [task.digest for task in tasks],
        "public_task_digests": [task.public.digest for task in tasks],
        "upstream_test_sha256": [sha(task.upstream_test.encode()) for task in tasks],
        "engine_source_digest": source_manifest()["digest"],
        "script_sha256": sha(Path(__file__).read_bytes()),
        "environment": {
            "python": platform.python_version(),
            "qiskit": version("qiskit"),
            "numpy": version("numpy"),
        },
        "calibration": "literal H/Z tensors, indexed CX; zero-input state is first column",
        "tolerance": 1e-14,
        "controls": probe(*tasks),
    }


def verify(report, cache):
    if canonical(report) != canonical(build(cache)):
        raise ValueError("Saved diagnostic differs from exact recreation")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build(args.cache)
    if args.check:
        verify(json.loads(args.output.read_bytes()), args.cache)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            [
                {key: row[key] for key in ("id", "bell_preparation", "normal", "hard")}
                for row in result["controls"]
            ],
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

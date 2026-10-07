"""Trusted authored-fixture calibration; never execute model-generated code here."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from matrix_semantics_controls import DIAGONAL_PARITY, IMPORTS, PAULI_PARITY
from qiskit.quantum_info import Operator, Pauli

from graybench.provenance import source_manifest


def authored(arguments, body):
    namespace = {}
    text = IMPORTS + f"def fixture({arguments}):\n"
    text += "".join("    " + line + "\n" for line in body.splitlines())
    exec(compile(text, "<trusted-authored-calibration-fixture>", "exec"), namespace)
    return namespace["fixture"]


def calibrate():
    evolution = authored("pauli_string,time", PAULI_PARITY)
    diagonal = authored("diag", DIAGONAL_PARITY)
    maximum_pauli, maximum_diagonal = 0.0, 0.0
    pauli_cases, diagonal_cases = 0, 0
    for width in range(1, 5):
        for chars in itertools.product("IXYZ", repeat=width):
            label = "".join(chars)
            # SDK Pauli conversion calibrates the separately authored basis/parity
            # implementation. The production oracle uses literal tensor matrices.
            matrix = Pauli(label).to_matrix()
            for time in (0.0, -0.23, 0.71):
                expected = np.cos(time) * np.eye(2**width) - 1j * np.sin(time) * matrix
                actual = Operator(evolution(label, time)).data
                assert np.isfinite(actual).all()
                error = float(np.max(np.abs(actual - expected)))
                maximum_pauli = max(maximum_pauli, error)
                assert error < 5e-12, (label, time, error)
                pauli_cases += 1
    rng = np.random.default_rng(251)
    for width in range(1, 6):
        for _ in range(16):
            values = np.exp(1j * rng.uniform(-np.pi, np.pi, 2**width))
            actual = Operator(diagonal(values.tolist())).data
            expected = np.diag(values)
            assert np.isfinite(actual).all()
            error = float(np.max(np.abs(actual - expected)))
            maximum_diagonal = max(maximum_diagonal, error)
            assert error < 5e-12, (width, error)
            diagonal_cases += 1
    return {
        "kind": "graybench_authored_matrix_alternative_calibration_v1",
        "scope": "Trusted authored algorithms; no graph, container, provider or model call",
        "engine_source_digest": source_manifest()["digest"],
        "fixture_source_sha256": hashlib.sha256(
            Path(__file__).with_name("matrix_semantics_controls.py").read_bytes()
        ).hexdigest(),
        "pauli": {
            "cases": pauli_cases,
            "widths": [1, 2, 3, 4],
            "times": [0.0, -0.23, 0.71],
            "maximum_entry_error": maximum_pauli,
        },
        "diagonal": {
            "cases": diagonal_cases,
            "widths": [1, 2, 3, 4, 5],
            "seed": 251,
            "maximum_entry_error": maximum_diagonal,
        },
        "absolute_entry_threshold": 5e-12,
        "phase_alignment": False,
        "publication_eligible": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = calibrate()
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

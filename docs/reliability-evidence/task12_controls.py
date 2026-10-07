"""Predeclare authored explicit-operator controls before isolated execution."""

import argparse
import json
import re
import textwrap
from pathlib import Path

from graybench.datasets import load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.task12_revision import BellOperatorJudge, revised_task

IMPORTS = (
    "import numpy as np\nfrom qiskit import QuantumCircuit\n"
    "from qiskit.quantum_info import Operator\n"
)
SDK = "circuit = QuantumCircuit(2)\ncircuit.h(0)\ncircuit.cx(0, 1)\n"
MATRIX = SDK + "matrix = Operator(circuit).data\n"
TENSOR = (
    "h = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)\n"
    "cx = np.array([[1, 0, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0]])\n"
    "return cx @ np.kron(np.eye(2), h)"
)
INDEXED = """matrix = np.zeros((4, 4), dtype=complex)
for column in range(4):
    before0, before1 = column & 1, column >> 1
    for after0 in range(2):
        after1 = before1 ^ after0
        row = (after1 << 1) | after0
        matrix[row, column] = (-1) ** (before0 * after0) / np.sqrt(2)
return matrix
"""


def probes(source):
    revised_task(source)
    result = [
        Probe(
            "canonical",
            "pass",
            "Exact original canonical implementation",
            source.canonical_solution,
        )
    ]
    rows = (
        ("literal-tensor", "pass", "Literal local H and CX matrices", TENSOR),
        ("indexed-basis", "pass", "Independent action on each input basis state", INDEXED),
        (
            "equivalent-gates",
            "pass",
            "Conjugate the mirrored construction with two SWAPs",
            "circuit = QuantumCircuit(2)\ncircuit.swap(0, 1)\ncircuit.h(1)\n"
            "circuit.cx(1, 0)\ncircuit.swap(0, 1)\nreturn Operator(circuit).data",
        ),
        (
            "global-phase",
            "pass",
            "Declared overall phase equivalence",
            MATRIX + "return np.exp(0.37j) * matrix",
        ),
        (
            "readonly",
            "pass",
            "Readonly returned numeric storage",
            MATRIX + "matrix.flags.writeable = False\nreturn matrix",
        ),
        (
            "strided",
            "pass",
            "Noncontiguous numeric view of owning storage",
            MATRIX + "return matrix.T.copy().T",
        ),
        (
            "real-array",
            "pass",
            "Real numeric representation of this real operator",
            MATRIX + "return matrix.real.copy()",
        ),
        (
            "external-buffer",
            "pass",
            "Logical values backed by Python bytes",
            MATRIX + "return np.frombuffer(matrix.tobytes(), dtype=matrix.dtype).reshape(4, 4)",
        ),
        (
            "dtype-metadata",
            "pass",
            "Unattested dtype metadata does not change values",
            MATRIX + "return matrix.astype(np.dtype(complex, metadata={'label': 'control'}))",
        ),
        (
            "large-backing",
            "pass",
            "Only the returned view values enter the wire budget",
            MATRIX + "backing = np.zeros(33000, dtype=complex)\nbacking[:16] = matrix.ravel()\n"
            "return backing[:16].reshape(4, 4)",
        ),
        (
            "big-endian",
            "pass",
            "Either declared byte order",
            MATRIX + "return matrix.astype('>c16')",
        ),
        (
            "negative-strides",
            "pass",
            "Logical values independent of negative strides",
            MATRIX + "return matrix[::-1, ::-1].copy()[::-1, ::-1]",
        ),
        (
            "complex64-phase",
            "pass",
            "An exactly representable phased operator at lower precision",
            MATRIX + "return np.round(matrix * np.exp(1j * np.pi / 4), 5).astype(np.complex64)",
        ),
        (
            "phase-tolerance-boundary",
            "pass",
            "Symmetric phase alignment at declared entry tolerance",
            MATRIX + "return matrix @ np.diag(np.exp(1j * np.array([1.2e-10, -1.2e-10, 0, 0])))",
        ),
        (
            "mirrored-preparation",
            "fail",
            "Same Bell zero-input state, different complete operator",
            "circuit = QuantumCircuit(2)\ncircuit.h(1)\ncircuit.cx(1, 0)\n"
            "return Operator(circuit).data",
        ),
        (
            "initial-z",
            "fail",
            "Initial Z leaves zero-input preparation unchanged",
            "circuit = QuantumCircuit(2)\ncircuit.z(1)\ncircuit.h(0)\n"
            "circuit.cx(0, 1)\nreturn Operator(circuit).data",
        ),
        (
            "column-phase",
            "fail",
            "Relative column phase, with correct first column",
            MATRIX + "return matrix @ np.diag([1, 1j, 1, 1])",
        ),
        (
            "first-column-only",
            "fail",
            "Only Bell preparation is correct",
            MATRIX + "matrix[:, 1:] = 0\nreturn matrix",
        ),
        ("identity", "fail", "Wrong complete action", "return np.eye(4, dtype=complex)"),
        (
            "scaled",
            "fail",
            "Global phase allowance does not allow magnitude scaling",
            MATRIX + "return 2 * matrix",
        ),
        ("transpose", "fail", "Wrong multiplication orientation", MATRIX + "return matrix.T"),
        (
            "wrong-shape",
            "fail",
            "Sixteen values with an incorrect shape",
            MATRIX + "return matrix.reshape(2, 8)",
        ),
        (
            "nested-list",
            "fail",
            "Return type is explicitly ndarray",
            MATRIX + "return matrix.tolist()",
        ),
        (
            "object-dtype",
            "unsupported",
            "Object elements are outside the numeric contract",
            MATRIX + "return matrix.astype(object)",
        ),
        ("nan", "fail", "Nonfinite matrix", MATRIX + "matrix[0, 0] = np.nan\nreturn matrix"),
        ("infinity", "fail", "Nonfinite matrix", MATRIX + "matrix[0, 0] = np.inf\nreturn matrix"),
        (
            "huge-finite",
            "fail",
            "Bound values before phase arithmetic",
            "return np.full((4, 4), complex(1e308, 1e308))",
        ),
        (
            "bell-minus",
            "fail",
            "Wrong Bell and complete action",
            SDK + "circuit.z(0)\nreturn Operator(circuit).data",
        ),
    )
    for name, expectation, rationale, body in rows:
        indented = textwrap.indent(IMPORTS + body + "\n", "    ")
        completion = (
            "\n" + indented
            if source.public.suite == "normal"
            else "def get_unitary():\n" + indented
        )
        result.append(Probe(name, expectation, rationale, completion))
    return tuple(result)


class ControlsJudge:
    def __init__(self, **kwargs):
        self.inner = BellOperatorJudge(**kwargs)

    def configuration(self, source):
        return self.inner.configuration(self.inner.revise(source))

    def evaluate(self, source, completion):
        return self.inner.evaluate(self.inner.revise(source), completion)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if re.fullmatch(r"sha256:[0-9a-f]{64}", args.image) is None:
        raise ValueError("Select an immutable Task 12 control image digest")
    sources = tuple(load_suite(suite, args.cache)[12] for suite in ("normal", "hard"))
    judge = ControlsJudge(image=args.image)
    declared = {f"{s.public.suite}/{s.public.task_id}": judge.configuration(s)[1] for s in sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(
        sources,
        judge,
        args.output,
        probes_for=lambda source: tuple(
            p for p in probes(source) if p.expectation != "unsupported"
        ),
        declared_judges=declared,
    )
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

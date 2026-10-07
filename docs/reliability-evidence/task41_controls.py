"""Predeclare explicit Pauli/subsystem controls before isolated execution."""

import argparse
import json
import re
import textwrap
from pathlib import Path

from graybench.datasets import load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.task41_revision import PauliSubsystemJudge, revised_task

IMPORTS = (
    "import numpy as np\nfrom qiskit import QuantumCircuit\n"
    "from qiskit.quantum_info import Operator, Pauli, DensityMatrix, SparsePauliOp\n"
)
SDK = (
    "identity = Operator(np.eye(8))\nlocal = Operator(Pauli('YX'))\n"
    "operator = identity.compose(local, qargs=[0, 2], front=True)\n"
)
TENSOR = (
    "x = np.array([[0, 1], [1, 0]])\n"
    "y = np.array([[0, -1j], [1j, 0]])\n"
    "return Operator(np.kron(np.kron(y, np.eye(2)), x))"
)
BASIS = """matrix = np.zeros((8, 8), dtype=complex)
for column in range(8):
    before0 = column & 1
    before1 = (column >> 1) & 1
    before2 = (column >> 2) & 1
    after0, after2 = 1 - before0, 1 - before2
    row = after0 + 2 * before1 + 4 * after2
    matrix[row, column] = 1j * (-1) ** before2
return Operator(matrix)
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
    rows = [
        (
            "compose-back",
            "pass",
            "Identity commutes; front is not a method obligation",
            SDK + "return identity.compose(local, qargs=[0, 2], front=False)",
        ),
        ("embedded-pauli", "pass", "Equivalent full Pauli label", "return Operator(Pauli('YIX'))"),
        (
            "reversed-local-description",
            "pass",
            "Different local label and reversed mapping produce the same complete operator",
            "return Operator(np.eye(8)).compose(Operator(Pauli('XY')), qargs=[2, 0])",
        ),
        (
            "circuit",
            "pass",
            "Equivalent explicit gate action",
            "circuit = QuantumCircuit(3)\ncircuit.x(0)\ncircuit.y(2)\nreturn Operator(circuit)",
        ),
        ("tensor", "pass", "Independent single-qubit tensor factors", TENSOR),
        ("basis-action", "pass", "Explicit complete action on all input basis states", BASIS),
        ("adjoint", "pass", "The specified Pauli is Hermitian", SDK + "return operator.adjoint()"),
        (
            "sparse-pauli",
            "pass",
            "Equivalent sparse construction",
            "return SparsePauliOp('YIX').to_operator()",
        ),
        (
            "readonly",
            "pass",
            "Storage writeability is ignored",
            SDK + "operator.data.flags.writeable = False\nreturn operator",
        ),
        (
            "strided",
            "pass",
            "Logical values independent of noncontiguous storage",
            SDK + "operator._data = operator.data.T.copy().T\nreturn operator",
        ),
        (
            "external-buffer",
            "pass",
            "Logical matrix stored in a Python bytes buffer",
            SDK + "operator._data = np.frombuffer(operator.data.tobytes(), "
            "dtype=complex).reshape(8, 8)\n"
            "return operator",
        ),
        (
            "dtype-metadata",
            "pass",
            "Numeric metadata is ignored",
            SDK + "operator._data = operator.data.astype(np.dtype(complex, "
            "metadata={'label': 'control'}))\n"
            "return operator",
        ),
        (
            "large-backing",
            "pass",
            "Backing allocation is not the logical result size",
            SDK + "backing = np.zeros(33000, dtype=complex)\nbacking[:64] = operator.data.ravel()\n"
            "operator._data = backing[:64].reshape(8, 8)\nreturn operator",
        ),
        (
            "big-endian",
            "pass",
            "Either declared byte order",
            SDK + "operator._data = operator.data.astype('>c16')\nreturn operator",
        ),
        (
            "complex64",
            "pass",
            "This exact operator is representable at the declared lower precision",
            SDK + "operator._data = operator.data.astype(np.complex64)\nreturn operator",
        ),
        (
            "binding-metadata",
            "pass",
            "Binding tags are explicitly outside the value contract",
            SDK + "return operator([2, 1, 0])",
        ),
        (
            "within-tolerance",
            "pass",
            "Declared absolute comparison, not a hidden exact-equality test",
            SDK + "operator.data[0, 0] = 5e-11\nreturn operator",
        ),
        (
            "xz-label",
            "fail",
            "Contradictory normal wording is resolved to YX",
            "return Operator(np.eye(8)).compose(Operator(Pauli('XZ')), qargs=[0, 2])",
        ),
        (
            "spectator-action",
            "fail",
            "The unselected qubit must be unchanged",
            "return Operator(Pauli('YXX'))",
        ),
        ("identity", "fail", "Wrong full operator", "return Operator(np.eye(8))"),
        ("zero", "fail", "Zero is not the specified operator", "return Operator(np.zeros((8, 8)))"),
        ("phase-minus", "fail", "Fixed Pauli phase", SDK + "return -operator"),
        ("phase-imaginary", "fail", "No global phase equivalence", SDK + "return 1j * operator"),
        (
            "small-wrong-phase",
            "fail",
            "A small but out-of-tolerance phase error",
            SDK + "return np.exp(1e-6j) * operator",
        ),
        ("scaled", "fail", "Wrong amplitude", SDK + "return 2 * operator"),
        (
            "transpose",
            "fail",
            "Y transpose has the opposite sign",
            SDK + "return Operator(operator.data.T)",
        ),
        (
            "conjugate",
            "fail",
            "Y conjugate has the opposite sign",
            SDK + "return Operator(operator.data.conj())",
        ),
        (
            "first-column-only",
            "fail",
            "All eight input basis states matter",
            SDK + "operator.data[:, 1:] = 0\nreturn operator",
        ),
        (
            "entry-error",
            "fail",
            "One out-of-tolerance matrix entry",
            SDK + "operator.data[0, 0] = 1e-6\nreturn operator",
        ),
        (
            "input-dimensions",
            "fail",
            "Correct matrix with wrong input subsystem factorization",
            SDK + "return Operator(operator.data, input_dims=(8,))",
        ),
        (
            "output-dimensions",
            "fail",
            "Correct matrix with wrong output subsystem factorization",
            SDK + "return Operator(operator.data, output_dims=(8,))",
        ),
        ("array", "fail", "Return category must be Operator", SDK + "return operator.data"),
        (
            "density-matrix",
            "fail",
            "Another numeric SDK category is not Operator",
            SDK + "return DensityMatrix(operator.data)",
        ),
        ("nan", "fail", "Nonfinite values", SDK + "operator.data[0, 0] = np.nan\nreturn operator"),
        (
            "infinity",
            "fail",
            "Nonfinite values",
            SDK + "operator.data[0, 0] = np.inf\nreturn operator",
        ),
        (
            "huge-finite",
            "fail",
            "Reject before unsafe numerical comparison",
            "return Operator(np.full((8, 8), 1e308 + 1e308j))",
        ),
        ("two-qubit", "fail", "Incorrect width", "return Operator(Pauli('YX'))"),
        (
            "object-dtype",
            "unsupported",
            "Outside-domain object matrix codec screen",
            SDK + "operator._data = operator.data.astype(object)\nreturn operator",
        ),
        (
            "forged-equality",
            "unsupported",
            "Outside-domain object with forged native equality",
            "class Forged:\n    def __eq__(self, other):\n        return True\nreturn Forged()",
        ),
    ]
    for positions in ((0, 1), (1, 0), (1, 2), (2, 0), (2, 1)):
        rows.append(
            (
                "placement-" + "-".join(map(str, positions)),
                "fail",
                "Wrong ordered local-to-global subsystem placement",
                "return Operator(np.eye(8)).compose(Operator(Pauli('YX')), "
                f"qargs={list(positions)})",
            )
        )
    for name, expectation, rationale, body in rows:
        indented = textwrap.indent(IMPORTS + body + "\n", "    ")
        completion = (
            "\n" + indented if source.public.suite == "normal" else "def compose_op():\n" + indented
        )
        result.append(Probe(name, expectation, rationale, completion))
    return tuple(result)


def semantic_probes(source):
    return tuple(p for p in probes(source) if p.expectation != "unsupported")


class ControlsJudge:
    def __init__(self, **kwargs):
        self.inner = PauliSubsystemJudge(**kwargs)

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
        raise ValueError("Select an immutable Task41 control image digest")
    sources = tuple(load_suite(suite, args.cache)[41] for suite in ("normal", "hard"))
    judge = ControlsJudge(image=args.image)
    declared = {f"{s.public.suite}/{s.public.task_id}": judge.configuration(s)[1] for s in sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(sources, judge, args.output, probes_for=semantic_probes, declared_judges=declared)
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

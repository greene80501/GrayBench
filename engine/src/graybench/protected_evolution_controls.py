"""Authored correct and wrong matrix-value algorithms; no private oracle imports."""

import ast
from textwrap import dedent, indent

from graybench.oracle_review import Probe
from graybench.protected_task116 import task116_value_task

EXPORT = "return [[[float(z.real), float(z.imag)] for z in row] for row in matrix]"
TENSOR = """import numpy as np
basis = {
    'I': np.eye(2, dtype=complex),
    'X': np.array([[0,1],[1,0]], dtype=complex),
    'Y': np.array([[0,-1j],[1j,0]], dtype=complex),
    'Z': np.array([[1,0],[0,-1]], dtype=complex),
}
pauli = np.ones((1,1), dtype=complex)
for char in pauli_string:
    pauli = np.kron(pauli, basis[char])
values, vectors = np.linalg.eigh(pauli)
matrix = (vectors * np.exp(-1j*time*values)) @ vectors.conj().T
"""
PARITY = """from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator
qc = QuantumCircuit(len(pauli_string))
active = [index for index, char in enumerate(reversed(pauli_string)) if char != 'I']
if not active:
    qc.global_phase = -time
else:
    for index in active:
        char = pauli_string[-1-index]
        if char == 'Y': qc.sdg(index)
        if char in 'XY': qc.h(index)
    pivot = active[-1]
    for index in active[:-1]: qc.cx(index, pivot)
    qc.rz(2*time, pivot)
    for index in reversed(active[:-1]): qc.cx(index, pivot)
    for index in reversed(active):
        char = pauli_string[-1-index]
        if char in 'XY': qc.h(index)
        if char == 'Y': qc.s(index)
matrix = Operator(qc).data
"""


def _canonical_body(source):
    if source.public.suite == "normal":
        return dedent(source.canonical_solution).strip()
    tree = ast.parse(source.canonical_solution)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == source.public.entry_point
    )
    lines = source.canonical_solution.splitlines()
    return dedent("\n".join(lines[function.body[0].lineno - 1 : function.body[-1].end_lineno]))


def evolution_probes(source):
    task116_value_task(source)  # Do not generate reference fixtures from a changed source.
    reference = (
        "from qiskit import QuantumCircuit\n"
        "from qiskit.circuit.library import PauliEvolutionGate\n"
        "from qiskit.quantum_info import Pauli, Operator\n"
        "from qiskit.synthesis import MatrixExponential\n"
        "def reference(pauli_string, time):\n"
        + indent(_canonical_body(source), "    ")
        + "\nmatrix = Operator(reference(pauli_string, time)).data\n"
    )
    rows = [
        (
            "canonical-export",
            "pass",
            "Original computation with explicit matrix-value export",
            reference,
        ),
        ("numpy-eigh", "pass", "Independent tensor/eigendecomposition algorithm", TENSOR),
        (
            "parity-rotations",
            "pass",
            "Equivalent circuit using only basis changes and parity rotations",
            PARITY,
        ),
        (
            "identity",
            "fail",
            "Ignores operator and time",
            "import numpy as np\nmatrix = np.eye(2**len(pauli_string), dtype=complex)\n",
        ),
        ("wrong-sign", "fail", "Reverses evolution direction", "time = -time\n" + TENSOR),
        ("double-time", "fail", "Evolution angle is doubled", "time = 2*time\n" + TENSOR),
        (
            "reverse-tensor",
            "fail",
            "Swaps little-endian tensor order",
            "pauli_string = pauli_string[::-1]\n" + TENSOR,
        ),
        ("transpose", "fail", "Transposes complex Pauli action", TENSOR + "matrix = matrix.T\n"),
        (
            "conjugate",
            "fail",
            "Conjugates time-dependent phases",
            TENSOR + "matrix = matrix.conj()\n",
        ),
        (
            "extra-phase",
            "fail",
            "Global phase is part of the declared action",
            TENSOR + "matrix *= np.exp(0.37j)\n",
        ),
        (
            "omit-identity-phase",
            "fail",
            "Drops evolution phase only on all-I inputs",
            TENSOR + "if set(pauli_string) == {'I'}: matrix = np.eye(len(matrix), dtype=complex)\n",
        ),
        ("scaled", "fail", "Magnitude must match the unitary action", TENSOR + "matrix *= 0.5\n"),
        (
            "large-finite",
            "fail",
            "Finite JSON components with overflowing complex error must fail safely",
            "import numpy as np\n"
            "matrix = np.full((2**len(pauli_string),)*2, complex(1.7e308, 1.7e308))\n",
        ),
        (
            "empty",
            "candidate_error",
            "No matrix value satisfies the public result shape",
            "return []\n",
        ),
        (
            "raw-ndarray",
            "candidate_error",
            "The declared answer uses JSON pairs, not native arrays",
            TENSOR + "return matrix\n",
        ),
    ]
    result = []
    for name, expectation, rationale, body in rows:
        if expectation != "candidate_error":
            body += EXPORT + "\n"
        completion = "\n" + indent(body, "    ")
        if source.public.suite == "hard":
            completion = "def evolution_matrix(pauli_string, time):" + completion
        result.append(Probe(name, expectation, rationale, completion))
    return tuple(result)

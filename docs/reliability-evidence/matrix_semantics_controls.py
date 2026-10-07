"""Authored matrix-semantic controls; no model generations or host candidate execution."""

import argparse
import ast
import json
import re
import textwrap
from pathlib import Path

from graybench.datasets import load_suite
from graybench.matrix_semantics import REVISIONS, CircuitMatrixJudge
from graybench.oracle_review import Probe, inspect_oracle_review, run_review

IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
IMPORTS = """import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Gate, Parameter
from qiskit.circuit.library import PauliEvolutionGate, HamiltonianGate, Diagonal
from qiskit.circuit.library import DiagonalGate, UnitaryGate, RXGate
from qiskit.synthesis import MatrixExponential
from qiskit.quantum_info import Pauli, Operator
from qiskit.converters import circuit_to_gate
"""

PAULI_PARITY = """qc = QuantumCircuit(len(pauli_string))
active = [index for index, char in enumerate(reversed(pauli_string)) if char != 'I']
if not active:
    qc.global_phase = -time
    return qc
for index in active:
    char = pauli_string[-1-index]
    if char == 'Y':
        qc.sdg(index)
    if char in 'XY':
        qc.h(index)
pivot = active[-1]
for index in active[:-1]:
    qc.cx(index, pivot)
qc.rz(2*time, pivot)
for index in reversed(active[:-1]):
    qc.cx(index, pivot)
for index in reversed(active):
    char = pauli_string[-1-index]
    if char in 'XY':
        qc.h(index)
    if char == 'Y':
        qc.s(index)
return qc"""

DIAGONAL_PARITY = """width = len(diag).bit_length()-1
phases = np.angle(np.asarray(diag,dtype=complex))
qc = QuantumCircuit(width)
for mask in range(len(diag)):
    coefficient = sum(
        phases[index] * (-1)**((mask & index).bit_count())
        for index in range(len(diag))
    ) / len(diag)
    active = [wire for wire in range(width) if mask & (1<<wire)]
    if not active:
        qc.global_phase += coefficient
        continue
    pivot = active[-1]
    for wire in active[:-1]:
        qc.cx(wire,pivot)
    qc.rz(-2*coefficient,pivot)
    for wire in reversed(active[:-1]):
        qc.cx(wire,pivot)
return qc"""

DIAGONAL = """width = len(diag).bit_length()-1
qc = QuantumCircuit(width)
qc.append(DiagonalGate(diag),range(width))
return qc"""


def canonical_body(source):
    if source.public.suite == "normal":
        return textwrap.dedent(source.canonical_solution).strip()
    tree = ast.parse(source.canonical_solution)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == source.public.entry_point
    )
    lines = source.canonical_solution.splitlines()
    return textwrap.dedent(
        "\n".join(lines[function.body[0].lineno - 1 : function.body[-1].end_lineno])
    )


def probes(source):
    number = int(source.public.task_id.rsplit("/", 1)[1])
    rows = [
        (
            "canonical",
            "pass",
            "Original computation with explicit control imports",
            canonical_body(source),
        )
    ]
    if number == 116:
        hamiltonian = (
            "qc = QuantumCircuit(len(pauli_string))\n"
            "qc.append(HamiltonianGate(Pauli(pauli_string).to_matrix(),time),"
            "range(len(pauli_string)))\nreturn qc"
        )
        rows += [
            (
                "parity-rotations",
                "pass",
                "Basis changes and parity rotations use no evolution synthesizer",
                PAULI_PARITY,
            ),
            ("hamiltonian", "pass", "Alternative Hamiltonian gate construction", hamiltonian),
            (
                "fixed-example",
                "fail",
                "Ignores both inputs",
                "qc = QuantumCircuit(1)\nqc.rx(2.0,0)\nreturn qc",
            ),
            (
                "negative-time",
                "fail",
                "Reverses evolution sign",
                hamiltonian.replace("to_matrix(),time", "to_matrix(),-time"),
            ),
            (
                "half-time",
                "fail",
                "Omits the rotation factor of two",
                hamiltonian.replace("to_matrix(),time", "to_matrix(),time/2"),
            ),
            (
                "reversed-order",
                "fail",
                "Reverses the Pauli tensor order",
                hamiltonian.replace("Pauli(pauli_string)", "Pauli(pauli_string[::-1])"),
            ),
            (
                "extra-phase",
                "fail",
                "Evolution includes global phase",
                hamiltonian.replace("return qc", "qc.global_phase = 0.37\nreturn qc"),
            ),
            (
                "identity",
                "fail",
                "Drops the input evolution",
                "return QuantumCircuit(len(pauli_string))",
            ),
        ]
    elif number == 120:
        rows += [
            ("diagonal-gate", "pass", "Direct supported diagonal gate", DIAGONAL),
            (
                "parity-phases",
                "pass",
                "Independent Walsh phase expansion uses only CX and RZ",
                DIAGONAL_PARITY,
            ),
            (
                "global-phase",
                "pass",
                "The contract permits an overall phase",
                DIAGONAL.replace("return qc", "qc.global_phase = 0.37\nreturn qc"),
            ),
            (
                "consume-input",
                "pass",
                "Mutation does not change the original expected action",
                DIAGONAL.replace("return qc", "diag.clear()\nreturn qc"),
            ),
            ("fixed-example", "fail", "Ignores input phases", "diag = [1,1j,-1,-1j]\n" + DIAGONAL),
            (
                "conjugated",
                "fail",
                "Negates the supplied phases",
                DIAGONAL.replace(
                    "DiagonalGate(diag)", "DiagonalGate([complex(v).conjugate() for v in diag])"
                ),
            ),
            (
                "reversed",
                "fail",
                "Reverses computational-basis order",
                DIAGONAL.replace("DiagonalGate(diag)", "DiagonalGate(diag[::-1])"),
            ),
            (
                "wrong-width",
                "fail",
                "Adds an extra qubit",
                DIAGONAL.replace("QuantumCircuit(width)", "QuantumCircuit(width+1)"),
            ),
            (
                "identity",
                "fail",
                "Drops the diagonal",
                "return QuantumCircuit(len(diag).bit_length()-1)",
            ),
            (
                "scaled",
                "fail",
                "A magnitude change is not global phase",
                DIAGONAL.replace(
                    "DiagonalGate(diag)", "UnitaryGate(0.5*np.diag(diag),check_input=False)"
                ),
            ),
            (
                "nonfinite",
                "fail",
                "Nonfinite matrix entries are invalid",
                DIAGONAL.replace(
                    "DiagonalGate(diag)",
                    "UnitaryGate(np.diag(diag)*float('nan'),check_input=False)",
                ),
            ),
        ]
    elif number == 125:
        rows += [
            ("to-gate", "pass", "Alternative circuit method", "return circ.to_gate()"),
            (
                "unitary-gate",
                "pass",
                "Gate subclasses and matrix constructions are allowed",
                "return UnitaryGate(Operator(circ).data)",
            ),
            (
                "mutate-input",
                "pass",
                "Original result is frozen before mutating input",
                "gate = circ.to_gate()\ncirc.data.clear()\nreturn gate",
            ),
            (
                "nested",
                "pass",
                "Explicit equivalent definition and phase",
                "qc = QuantumCircuit(circ.num_qubits)\n"
                "qc.append(circ.to_gate(),range(circ.num_qubits))\n"
                "qc.global_phase = 0.37\nreturn qc.to_gate()",
            ),
            (
                "historical-shape-only",
                "fail",
                "The first original gate action was not checked",
                "qc = QuantumCircuit(circ.num_qubits)\n"
                "if circ.num_qubits == 1:\n    qc.z(0)\nreturn qc.to_gate()",
            ),
            (
                "identity",
                "fail",
                "Preserves width but discards action",
                "return QuantumCircuit(circ.num_qubits).to_gate()",
            ),
            (
                "inverse",
                "fail",
                "Returns the opposite operation",
                "return circ.inverse().to_gate()",
            ),
            (
                "reversed-wires",
                "fail",
                "Changes little-endian wire order",
                "return circ.reverse_bits().to_gate()",
            ),
            (
                "transposed",
                "fail",
                "Transposition differs on complex sequences",
                "return UnitaryGate(Operator(circ).data.T)",
            ),
            (
                "conjugated",
                "fail",
                "Conjugates phase and rotations",
                "return UnitaryGate(Operator(circ).data.conj())",
            ),
            (
                "wrong-width",
                "fail",
                "Adds a qubit",
                "return QuantumCircuit(circ.num_qubits+1).to_gate()",
            ),
            ("wrong-type", "fail", "A circuit is not a Gate value", "return circ.copy()"),
            (
                "unbound",
                "fail",
                "Returned gate must be numeric",
                "return RXGate(Parameter('theta'))",
            ),
            (
                "scaled",
                "fail",
                "Invalid operator magnitude",
                "return UnitaryGate(0.5*Operator(circ).data,check_input=False)",
            ),
            (
                "nonfinite",
                "fail",
                "Nonfinite operator",
                "return UnitaryGate(Operator(circ).data*float('nan'),check_input=False)",
            ),
        ]
    else:
        raise ValueError("No matrix control roster for this source")
    output = []
    for name, expectation, rationale, body in rows:
        lines = IMPORTS + body
        indented = textwrap.indent(lines, "    ")
        if source.public.suite == "normal":
            completion = "\n" + indented
        else:
            arguments = REVISIONS[
                next(track for track, record in REVISIONS.items() if record[0] == number)
            ][2]
            completion = f"def {source.public.entry_point}({arguments}):\n" + indented
        output.append(Probe(name, expectation, rationale, completion))
    return tuple(output)


class MatrixControlsJudge:
    def __init__(self, track, **kwargs):
        self.inner = CircuitMatrixJudge(track, **kwargs)

    def configuration(self, source):
        return self.inner.configuration(self.inner.revise(source))

    def evaluate(self, source, completion):
        return self.inner.evaluate(self.inner.revise(source), completion)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation-recipe", choices=tuple(REVISIONS), required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if re.fullmatch(r"sha256:[0-9a-f]{64}", args.image) is None:
        raise ValueError("Select an immutable matrix-control image digest")
    number = REVISIONS[args.evaluation_recipe][0]
    sources = tuple(load_suite(suite, args.cache)[number] for suite in ("normal", "hard"))
    judge = MatrixControlsJudge(args.evaluation_recipe, image=args.image)
    declared = {f"{s.public.suite}/{s.public.task_id}": judge.configuration(s)[1] for s in sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(sources, judge, args.output, probes_for=probes, declared_judges=declared)
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

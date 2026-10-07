"""Predeclare fixed authored Task 11 controls before isolated execution."""

import argparse
import json
import re
import textwrap
from pathlib import Path

from graybench.datasets import load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.task11_revision import StatevectorActionJudge, revised_task

IMPORTS = (
    "import numpy as np\nfrom qiskit import QuantumCircuit\n"
    "from qiskit.quantum_info import Statevector, Operator\n"
)
INDEXED = """width = circuit.num_qubits
state = np.zeros(2**width, dtype=complex)
state[0] = 1
for instruction in circuit.data:
    wires = [circuit.find_bit(q).index for q in instruction.qubits]
    matrix = Operator(instruction.operation).data
    output = np.zeros_like(state)
    mask = sum(1 << wire for wire in wires)
    for column, amplitude in enumerate(state):
        local_column = sum(((column >> wire) & 1) << bit for bit, wire in enumerate(wires))
        for local_row in range(2**len(wires)):
            row = column & ~mask
            row |= sum(((local_row >> bit) & 1) << wire for bit, wire in enumerate(wires))
            output[row] += matrix[local_row, local_column] * amplitude
    state = output
return Statevector(np.exp(1j * float(circuit.global_phase)) * state, dims=(2,) * width)
"""


def probes(source):
    revised_task(source)  # Exact pinned identity, including original/reference bytes.
    rows = (
        (
            "canonical",
            "pass",
            "SDK state simulation",
            "return Statevector.from_instruction(circuit)",
        ),
        (
            "operator-column",
            "pass",
            "First column of the full operator",
            "return Statevector(Operator(circuit).data[:, 0], dims=(2,) * circuit.num_qubits)",
        ),
        ("indexed-simulator", "pass", "Independent basis-index gate application", INDEXED),
        (
            "global-phase",
            "pass",
            "Declared unit-modulus phase equivalence",
            "return Statevector(np.exp(0.23j) * Statevector.from_instruction(circuit).data, "
            "dims=(2,) * circuit.num_qubits)",
        ),
        (
            "consume-input",
            "pass",
            "Result freezes original action before permitted mutation",
            "state = Statevector.from_instruction(circuit)\ncircuit.data.clear()\nreturn state",
        ),
        (
            "fixed-upstream-example",
            "fail",
            "Ignores the input; original checks accept it",
            "fixed = QuantumCircuit(2)\nfixed.u(0.39702, 0.238798, 0.298374, 0)\n"
            "fixed.cx(0, 1)\nreturn Statevector.from_instruction(fixed)",
        ),
        (
            "always-zero",
            "fail",
            "Preserves width but discards action",
            "return Statevector.from_int(0, dims=(2,) * circuit.num_qubits)",
        ),
        (
            "reversed-wires",
            "fail",
            "Wrong computational-basis bit order",
            "return Statevector.from_instruction(circuit.reverse_bits())",
        ),
        (
            "conjugated",
            "fail",
            "Wrong relative complex phases",
            "return Statevector(Statevector.from_instruction(circuit).data.conj(), "
            "dims=(2,) * circuit.num_qubits)",
        ),
        (
            "inverse",
            "fail",
            "Simulates opposite circuit action",
            "return Statevector.from_instruction(circuit.inverse())",
        ),
        (
            "scaled",
            "fail",
            "Invalid state magnitude",
            "return Statevector(0.5 * Statevector.from_instruction(circuit).data, "
            "dims=(2,) * circuit.num_qubits)",
        ),
        (
            "wrong-width",
            "fail",
            "Adds a subsystem",
            "return Statevector.from_int(0, dims=(2,) * (circuit.num_qubits + 1))",
        ),
        (
            "wrong-type",
            "fail",
            "Array is not a Statevector value",
            "return Statevector.from_instruction(circuit).data",
        ),
        (
            "nonfinite",
            "fail",
            "Nonfinite amplitudes",
            "return Statevector(np.full(2**circuit.num_qubits, complex(float('nan'), 0)), "
            "dims=(2,) * circuit.num_qubits)",
        ),
        (
            "huge-finite",
            "fail",
            "Bound before unsafe complex phase arithmetic",
            "return Statevector(np.full(2**circuit.num_qubits, complex(1.7e308, 1.7e308)), "
            "dims=(2,) * circuit.num_qubits)",
        ),
        (
            "clear-before-simulation",
            "fail",
            "Reports the changed action instead of the original",
            "circuit.data.clear()\nreturn Statevector.from_instruction(circuit)",
        ),
    )
    result = []
    for name, expectation, rationale, body in rows:
        indented = textwrap.indent(IMPORTS + body + "\n", "    ")
        completion = (
            "\n" + indented
            if source.public.suite == "normal"
            else "def get_statevector(circuit):\n" + indented
        )
        result.append(Probe(name, expectation, rationale, completion))
    return tuple(result)


class ControlsJudge:
    def __init__(self, **kwargs):
        self.inner = StatevectorActionJudge(**kwargs)

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
        raise ValueError("Select an immutable Task 11 control image digest")
    sources = tuple(load_suite(suite, args.cache)[11] for suite in ("normal", "hard"))
    judge = ControlsJudge(image=args.image)
    declared = {f"{s.public.suite}/{s.public.task_id}": judge.configuration(s)[1] for s in sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(sources, judge, args.output, probes_for=probes, declared_judges=declared)
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

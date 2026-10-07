"""Fixed authored state/measurement controls, predeclared before isolated execution."""

import argparse
import json
import re
import textwrap
from pathlib import Path

from graybench.datasets import load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.task66_revision import WMeasurementJudge, revised_task

IMPORTS = (
    "import numpy as np\nfrom qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister\n"
    "from qiskit.circuit import ControlledGate, Gate, Instruction, Parameter\n"
    "from qiskit.circuit.library import UnitaryGate\n"
)
GATES = (
    "circuit = QuantumCircuit(3)\n"
    "circuit.ry(2*np.arccos(1/np.sqrt(3)),0)\ncircuit.ch(0,1)\n"
    "circuit.cx(1,2)\ncircuit.cx(0,1)\ncircuit.x(0)\n"
)
VECTOR = "vector = np.zeros(8,dtype=complex)\nvector[[1,2,4]] = 1/np.sqrt(3)\n"
MEASURE = "circuit.measure_all()\nreturn circuit"


def probes(source):
    revised_task(source)
    result = [
        Probe(
            "canonical", "pass", "Exact original canonical construction", source.canonical_solution
        )
    ]
    rows = [
        (
            "amplitudes",
            "pass",
            "Independent amplitude preparation",
            VECTOR + "circuit = QuantumCircuit(3)\ncircuit.prepare_state(vector)\n" + MEASURE,
        ),
        (
            "initialize",
            "pass",
            "Deterministic initialization is allowed",
            VECTOR + "circuit = QuantumCircuit(3)\ncircuit.initialize(vector)\n" + MEASURE,
        ),
        (
            "reset-prefix",
            "pass",
            "Reset before preparing the target is allowed",
            "circuit = QuantumCircuit(3)\ncircuit.h(0)\ncircuit.reset(range(3))\n"
            + VECTOR
            + "circuit.prepare_state(vector)\n"
            + MEASURE,
        ),
        (
            "global-phase",
            "pass",
            "Global phase does not change the density matrix",
            GATES + "circuit.global_phase = 0.37\n" + MEASURE,
        ),
        (
            "wire-permutation",
            "pass",
            "The symmetric state is invariant under wire permutation",
            GATES + "circuit.swap(0,2)\n" + MEASURE,
        ),
        (
            "householder",
            "pass",
            "Independent full unitary mapping zero to W",
            VECTOR
            + (
                "zero = np.zeros(8,dtype=complex)\nzero[0] = 1\nv = (zero-vecto"
                "r)/np.sqrt(2)\nmatrix = np.eye(8)-2*np.outer(v,v.conj())\ncirc"
                "uit = QuantumCircuit(3)\ncircuit.append(UnitaryGate(matrix),r"
                "ange(3))\n"
            )
            + MEASURE,
        ),
        (
            "named-registers",
            "pass",
            "Arbitrary register names and bit mapping",
            GATES
            + (
                "circuit.add_register(ClassicalRegister(5,'output'))\ncircuit."
                "measure([2,0,1],[4,0,2])\nreturn circuit"
            ),
        ),
        (
            "metadata",
            "pass",
            "Names and metadata do not affect the contract",
            GATES
            + "circuit.name = 'authored-name'\ncircuit.metadata = {'tag':'fixture','value':7}\n"
            + MEASURE,
        ),
        (
            "bound-parameter",
            "pass",
            "A fully bound identity rotation is allowed",
            GATES
            + (
                "theta = Parameter('theta')\ncircuit.rz(theta,0)\ncircuit = cir"
                "cuit.assign_parameters({theta:0})\n"
            )
            + MEASURE,
        ),
        (
            "post-measure-barriers",
            "pass",
            "Barriers after measurement are allowed",
            GATES + "circuit.measure_all()\ncircuit.barrier()\nreturn circuit",
        ),
        ("zero", "fail", "Wrong prepared state", "circuit = QuantumCircuit(3)\n" + MEASURE),
        (
            "single-excitation",
            "fail",
            "Only one excitation location populated",
            "circuit = QuantumCircuit(3)\ncircuit.x(0)\n" + MEASURE,
        ),
        (
            "product",
            "fail",
            "Product superposition has wrong density",
            "circuit = QuantumCircuit(3)\ncircuit.h(range(3))\n" + MEASURE,
        ),
        (
            "ghz",
            "fail",
            "Wrong entangled state",
            "circuit = QuantumCircuit(3)\ncircuit.h(0)\ncircuit.cx(0,1)\ncircuit.cx(1,2)\n"
            + MEASURE,
        ),
        (
            "unequal-populations",
            "fail",
            "Wrong relative amplitudes",
            (
                "vector = np.zeros(8,dtype=complex)\nvector[[1,2,4]] = [0.5,0."
                "5,np.sqrt(0.5)]\ncircuit = QuantumCircuit(3)\ncircuit.prepare_"
                "state(vector)\n"
            )
            + MEASURE,
        ),
        (
            "relative-i",
            "fail",
            "Wrong relative phase despite correct probabilities",
            GATES + "circuit.s(1)\n" + MEASURE,
        ),
        (
            "orthogonal-phases",
            "fail",
            "Orthogonal state with the same populations",
            GATES + "circuit.p(2*np.pi/3,1)\ncircuit.p(4*np.pi/3,2)\n" + MEASURE,
        ),
        (
            "missing-measurement",
            "fail",
            "One qubit is not measured",
            GATES
            + (
                "circuit.add_register(ClassicalRegister(3))\ncircuit.measure(["
                "0,1],[0,1])\nreturn circuit"
            ),
        ),
        (
            "duplicate-qubit",
            "fail",
            "One qubit measured twice, another omitted",
            GATES
            + (
                "circuit.add_register(ClassicalRegister(3))\ncircuit.measure(["
                "0,1,0],[0,1,2])\nreturn circuit"
            ),
        ),
        (
            "shared-classical-bit",
            "fail",
            "Two qubits write the same classical bit",
            GATES
            + (
                "circuit.add_register(ClassicalRegister(3))\ncircuit.measure(["
                "0,1,2],[0,0,2])\nreturn circuit"
            ),
        ),
        (
            "repeated-measurement",
            "fail",
            "Four rather than three measurements",
            GATES + "circuit.measure_all()\ncircuit.measure(2,2)\nreturn circuit",
        ),
        (
            "identity-after-measurement",
            "fail",
            "Preparation operations after measurement are forbidden even if net identity",
            GATES + "circuit.measure_all()\ncircuit.z(0)\ncircuit.z(0)\nreturn circuit",
        ),
        (
            "reset-after-measurement",
            "fail",
            "Reset after measuring is forbidden",
            GATES + "circuit.measure_all()\ncircuit.reset(0)\nreturn circuit",
        ),
        (
            "delay",
            "fail",
            "Timing instructions are outside the admitted prefix",
            GATES + "circuit.delay(100,0)\n" + MEASURE,
        ),
        (
            "unbound",
            "fail",
            "An unbound rotation does not specify the target",
            GATES + "circuit.rz(Parameter('theta'),0)\n" + MEASURE,
        ),
        ("four-qubits", "fail", "Wrong circuit width", "circuit = QuantumCircuit(4)\n" + MEASURE),
        (
            "too-many-bits",
            "fail",
            "Declared classical resource bound exceeded",
            GATES
            + (
                "circuit.add_register(ClassicalRegister(65))\ncircuit.measure("
                "[0,1,2],[0,1,2])\nreturn circuit"
            ),
        ),
        ("no-bits", "fail", "No measurements or classical bits", GATES + "return circuit"),
        (
            "missing-definition",
            "fail",
            "Generic instruction with no permitted definition",
            GATES + "circuit.append(Instruction('authored-unknown',3,0,[]),range(3))\n" + MEASURE,
        ),
        (
            "instruction-bound",
            "fail",
            "More than 1024 visited instruction entries",
            GATES
            + "circuit.measure_all()\nfor _ in range(1024):\n    circuit.barrier()\nreturn circuit",
        ),
    ]
    for wire in range(3):
        rows.append(
            (
                f"relative-minus-{wire}",
                "fail",
                "Wrong relative phase with unchanged populations",
                GATES + f"circuit.z({wire})\n" + MEASURE,
            )
        )
    for control_state in (0, 1):
        for phase in (0, 0.37):
            body = (
                "base = QuantumCircuit(2)\nbase.cx(0,1)\nbase.cx(0,1)\n"
                + f"base.global_phase = {phase}\n"
                + "controlled = base.to_gate().control(1,"
                + f"ctrl_state={control_state},annotated=False)\n"
                + GATES
                + "circuit.append(controlled,range(3))\n"
                + MEASURE
            )
            rows.append(
                (
                    f"controlled-{control_state}-phase-{phase}",
                    "fail" if phase else "pass",
                    "Base global phase becomes relative under quantum control",
                    body,
                )
            )
    rows.append(
        (
            "controlled-instruction-bound",
            "fail",
            "Generic ControlledGate cannot hide more than 1024 definition entries",
            "body = QuantumCircuit(3)\nfor _ in range(1025):\n    body.id(1)\n"
            "base = QuantumCircuit(2).to_gate()\n"
            "wrapped = ControlledGate('authored',3,[],definition=body,base_gate=base)\n"
            + GATES
            + "circuit.append(wrapped,range(3))\n"
            + MEASURE,
        )
    )
    for name, classical, constructor in (
        ("generic-gate", False, "Gate('authored',3,[])"),
        ("generic-instruction", False, "Instruction('authored',3,0,[])"),
        ("nested-measurements", True, "Instruction('authored',3,3,[])"),
    ):
        body = GATES + ("circuit.measure_all()\n" if classical else "")
        body += f"wrapped = {constructor}\nwrapped.definition = circuit\n"
        body += (
            "circuit = QuantumCircuit(3,3)\ncircuit.append(wrapped,[2,0,1],[1,2,0])\nreturn circuit"
            if classical
            else "circuit = QuantumCircuit(3)\ncircuit.append(wrapped,[2,0,1])\n" + MEASURE
        )
        rows.append((name, "pass", "Explicit composite definition preserves the contract", body))
    for name, expectation, rationale, body in rows:
        code = textwrap.indent(IMPORTS + body + "\n", "    ")
        completion = "\n" + code if source.public.suite == "normal" else "def w_state():\n" + code
        result.append(Probe(name, expectation, rationale, completion))
    return tuple(result)


class ControlsJudge:
    def __init__(self, **kwargs):
        self.inner = WMeasurementJudge(**kwargs)

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
        raise ValueError("Use an immutable Task66 control image")
    sources = tuple(load_suite(suite, args.cache)[66] for suite in ("normal", "hard"))
    judge = ControlsJudge(image=args.image)
    declared = {f"{s.public.suite}/{s.public.task_id}": judge.configuration(s)[1] for s in sources}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(sources, judge, args.output, probes_for=probes, declared_judges=declared)
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

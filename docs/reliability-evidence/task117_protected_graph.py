"""Predeclared authored controls for the two-qubit unitary/basis condition."""

import argparse
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.task117_revision import NESTED_TRACK, TRACK, UnitaryBasisJudge, revised_task

IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
DIRECT = "qc = TwoQubitBasisDecomposer(CXGate())(unitary)\n"
IMPORTS = (
    "from qiskit import QuantumCircuit\nfrom qiskit.synthesis import TwoQubitBasisDecomposer\n"
    "from qiskit.quantum_info import Operator\nfrom qiskit.circuit.library import CXGate\n"
    "import numpy as np\n"
)
QR_BODY = """def controlled_local(matrix, control, target, control_value):
    # U = exp(i*alpha) Rz(phi) Ry(theta) Rz(lam).
    alpha = np.angle(np.linalg.det(matrix)) / 2
    local = matrix * np.exp(-1j*alpha)
    theta = 2*np.arctan2(abs(local[1,0]), abs(local[0,0]))
    phi = np.angle(local[1,0]) - np.angle(local[0,0])
    lam = -np.angle(local[1,0]) - np.angle(local[0,0])
    if control_value == 0:
        qc.x(control)
    # ABC=I and AXBXC=Rz(phi)Ry(theta)Rz(lam).
    qc.rz((lam-phi)/2, target)
    qc.cx(control, target)
    qc.rz(-(phi+lam)/2, target)
    qc.ry(-theta/2, target)
    qc.cx(control, target)
    qc.ry(theta/2, target)
    qc.rz(phi, target)
    qc.p(alpha, control)
    if control_value == 0:
        qc.x(control)

qc = QuantumCircuit(2)
order = [0,1,3,2]  # Adjacent Gray-code rows differ in just one qubit.
working = unitary.data[np.ix_(order, order)].copy()
eliminations = []
for col in range(3):
    for row in range(3, col, -1):
        a, b = working[row-1,col], working[row,col]
        radius = np.hypot(abs(a), abs(b))
        if radius < 1e-14:
            continue
        givens = np.array([[a.conjugate(), b.conjugate()], [-b,a]]) / radius
        working[[row-1,row],:] = givens @ working[[row-1,row],:]
        eliminations.append((order[row-1], order[row], givens.conj().T))
phases = np.empty(4)
for index, original in enumerate(order):
    phases[original] = np.angle(working[index,index])
qc.global_phase = phases[0]
qc.p(phases[1]-phases[0], 0)
qc.p(phases[2]-phases[0], 1)
angle = phases[3]-phases[1]-phases[2]+phases[0]
qc.p(angle/2, 0)
qc.p(angle/2, 1)
qc.cx(0, 1)
qc.p(-angle/2, 1)
qc.cx(0, 1)
for first, second, matrix in reversed(eliminations):
    target = (first ^ second).bit_length()-1
    control = 1-target
    if (first >> target) & 1:
        matrix = matrix[np.ix_([1,0],[1,0])]
    controlled_local(matrix, control, target, (first >> control) & 1)
return qc
"""
OPEN_CONTROL_BODY = (
    DIRECT
    + """output = qc.copy_empty_like()
for item in qc.data:
    wires = tuple(qc.find_bit(q).index for q in item.qubits)
    if isinstance(item.operation, CXGate):
        {before}
        output.append(CXGate(ctrl_state=0), wires)
        {after}
    else:
        output.append(item.operation, wires)
return output
"""
)


class Task117GraphJudge:
    def __init__(self, *, image, docker="docker", track=TRACK):
        self.inner = UnitaryBasisJudge(image=image, docker=docker, track=track)

    def configuration(self, source):
        return self.inner.configuration(revised_task(source))

    def evaluate(self, source, completion):
        return self.inner.evaluate(revised_task(source), completion)


def probes(source):
    revised_task(source)
    controls = (
        ("direct", "pass", "The requested SDK decomposer", DIRECT + "return qc"),
        (
            "qr-givens",
            "pass",
            "Independently derived two-level QR and controlled rotations",
            QR_BODY,
        ),
        (
            "zyz-basis",
            "pass",
            "A different local Euler basis",
            "return TwoQubitBasisDecomposer(CXGate(), euler_basis='ZYZ')(unitary)",
        ),
        (
            "transpile-basis",
            "pass",
            "A separately authored synthesis pipeline",
            "from qiskit import transpile\nqc = QuantumCircuit(2)\n"
            "qc.unitary(unitary, [0, 1])\n"
            "return transpile(qc, basis_gates=['rz','sx','cx'], optimization_level=0)",
        ),
        (
            "nested-phase",
            "pass",
            "Explicit definitions, unused bits and global phase",
            DIRECT + "outer = QuantumCircuit(2, 1)\nouter.append(qc.to_gate(), [0, 1])\n"
            "outer.barrier()\nouter.global_phase += 0.63\nreturn outer",
        ),
        (
            "mutate-input",
            "pass",
            "The result describes the original input",
            DIRECT + "unitary.data[:] = np.eye(4)\nreturn qc",
        ),
        (
            "within-tolerance",
            "pass",
            "A small unitary perturbation is accepted",
            DIRECT + "qc.rz(1e-10, 0)\nreturn qc",
        ),
        (
            "open-control-equivalent",
            "pass",
            "Actual open-control CX values are respected",
            OPEN_CONTROL_BODY.format(before="output.x(wires[0])", after="output.x(wires[0])"),
        ),
        (
            "local-composite",
            "pass",
            "Local explicit definitions and phases are expanded",
            DIRECT + "from qiskit.circuit import Gate\nlocal = QuantumCircuit(1)\n"
            "local.h(0)\nlocal.h(0)\nlocal.global_phase = 0.37\n"
            "gate = Gate('explicit-local', 1, [])\ngate.definition = local\n"
            "qc.append(gate, [0])\nqc.global_phase -= 0.37\nreturn qc",
        ),
        (
            "constant-cx",
            "fail",
            "The original input-independent false pass",
            "qc = QuantumCircuit(2)\nqc.cx(0, 1)\nreturn qc",
        ),
        ("constant-identity", "fail", "The supplied operator matters", "return QuantumCircuit(2)"),
        (
            "measurement",
            "fail",
            "Measurement is not a unitary decomposition",
            DIRECT + "from qiskit import ClassicalRegister\n"
            "qc.add_register(ClassicalRegister(1, 'readout'))\nqc.measure(0, 0)\nreturn qc",
        ),
        ("reset", "fail", "Reset is not unitary", DIRECT + "qc.reset(0)\nreturn qc"),
        (
            "transpose",
            "fail",
            "Transposing the input changes the requested operator",
            "return TwoQubitBasisDecomposer(CXGate())(Operator(unitary.data.T))",
        ),
        (
            "conjugate",
            "fail",
            "Conjugating the input changes the requested operator",
            "return TwoQubitBasisDecomposer(CXGate())(Operator(unitary.data.conj()))",
        ),
        (
            "inverse",
            "fail",
            "Inverting the input changes the requested operator",
            "return TwoQubitBasisDecomposer(CXGate())(Operator(unitary.data.conj().T))",
        ),
        (
            "wrong-wires",
            "fail",
            "Qubit order must be retained",
            DIRECT + "return qc.reverse_bits()",
        ),
        (
            "outside-tolerance",
            "fail",
            "A meaningful relative-phase error is rejected",
            DIRECT + "qc.rz(1e-5, 0)\nreturn qc",
        ),
        (
            "opaque-matrix",
            "fail",
            "The judge must not do missing synthesis",
            "qc = QuantumCircuit(2)\nqc.unitary(unitary, [0, 1])\nreturn qc",
        ),
        ("wrong-width", "fail", "Exactly two qubits", "return QuantumCircuit(3)"),
        ("wrong-type", "fail", "Circuit output is required", "return unitary"),
        (
            "unbound",
            "fail",
            "An unbound rotation is not a numeric decomposition",
            DIRECT
            + "from qiskit.circuit import Parameter\nqc.rx(Parameter('theta'), 0)\nreturn qc",
        ),
        (
            "changed-control-state",
            "fail",
            "An uncompensated open-control replacement is wrong",
            OPEN_CONTROL_BODY.format(before="pass", after="pass"),
        ),
        (
            "nested-timing",
            "fail",
            "Local composite leaves obey the same no-timing rule",
            DIRECT + "from qiskit.circuit import Gate\nlocal = QuantumCircuit(1)\n"
            "local.delay(123, 0, unit='dt')\ngate = Gate('local-delay', 1, [])\n"
            "gate.definition = local\nqc.append(gate, [0])\nreturn qc",
        ),
    )
    output = []
    for name, expectation, rationale, body in controls:
        indented = "".join(f"    {line}\n" for line in body.splitlines())
        completion = (
            "\n" + indented
            if source.public.suite == "normal"
            else IMPORTS + "def decompose_unitary(unitary):\n" + indented
        )
        output.append(Probe(name, expectation, rationale, completion))
    return tuple(output)


def nested_probes(source):
    """The original controls plus every allowed circuit-definition depth."""
    original = probes(source)
    output = []
    for levels in range(16):
        body = DIRECT + (
            "from qiskit.circuit import Gate\n"
            f"for index in range({levels}):\n"
            "    gate = Gate('supplied-level-' + str(index), 2, [])\n"
            "    gate.definition = qc\n"
            "    wrapper = QuantumCircuit(2)\n"
            "    wrapper.append(gate, [0, 1])\n"
            "    wrapper.global_phase = 0.173\n"
            "    qc = wrapper\n"
            "return qc"
        )
        indented = "".join(f"    {line}\n" for line in body.splitlines())
        completion = (
            "\n" + indented
            if source.public.suite == "normal"
            else IMPORTS + "def decompose_unitary(unitary):\n" + indented
        )
        output.append(
            Probe(
                f"definition-depth-{levels}",
                "pass",
                f"{levels + 1} circuit levels retain the input operator up to global phase",
                completion,
            )
        )
    return original + tuple(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evaluation-recipe", choices=(TRACK, NESTED_TRACK), default=TRACK)
    args = parser.parse_args()
    if args.image != IMAGE:
        raise ValueError("Expected the pinned task-117 image")
    sources = tuple(load_suite(suite, args.cache)[117] for suite in ("normal", "hard"))
    judge = Task117GraphJudge(image=args.image, track=args.evaluation_recipe)
    declared = {
        f"{source.public.suite}/{source.public.task_id}": judge.configuration(source)[1]
        for source in sources
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(
        sources,
        judge,
        args.output,
        probes_for=nested_probes if args.evaluation_recipe == NESTED_TRACK else probes,
        declared_judges=declared,
    )
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

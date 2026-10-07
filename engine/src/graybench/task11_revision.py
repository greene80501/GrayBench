"""Source-bound Task 11 state action; native provenance is not attested."""

from graybench.graph_limits import GraphLimits
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.task11_sources import SOURCE_RECORDS
from graybench.upstream import UpstreamJudge

TRACK = "qhe11-statevector-action-graph-v1"
REQUIREMENT = (
    "Given a numeric unitary Qiskit QuantumCircuit on one to five qubits with no "
    "classical bits or unbound parameters, return a Statevector representing its "
    "action on the all-zero computational basis state, in Qiskit's little-endian "
    "computational-basis order. Its dimension must match the original circuit and "
    "its subsystem dimensions must each be two. Equivalent gate constructions and "
    "an overall unit-modulus global phase in the returned state are allowed. "
    "After phase alignment, amplitudes use absolute tolerance 1e-10 and zero relative "
    "tolerance. Amplitudes must be finite. You may modify the input, but the returned "
    "state must describe its original action. Native object provenance and internal "
    "simulation methods are not attested."
)

CASE_FACTORY = """def statevector_cases():
    import numpy as np
    from qiskit import QuantumCircuit, QuantumRegister
    from qiskit.circuit import Gate, Parameter
    from qiskit.quantum_info import Statevector

    x = np.array([[0, 1], [1, 0]], dtype=complex)
    h = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
    s = np.diag([1, 1j])
    cases = []

    def local(matrix, width, wire):
        result = np.ones((1, 1), dtype=complex)
        for index in reversed(range(width)):
            result = np.kron(result, matrix if index == wire else np.eye(2))
        return result

    def cx(width, control, target):
        result = np.zeros((2**width, 2**width), dtype=complex)
        for column in range(2**width):
            row = column ^ (1 << target) if column & (1 << control) else column
            result[row, column] = 1
        return result

    def u(theta, phi, lam):
        c, t = np.cos(theta / 2), np.sin(theta / 2)
        return np.array([[c, -np.exp(1j * lam) * t],
                         [np.exp(1j * phi) * t, np.exp(1j * (phi + lam)) * c]])

    for width in range(1, 6):
        cases.append((QuantumCircuit(width), np.eye(2**width, dtype=complex)))
        for wire in sorted({0, width - 1}):
            circuit = QuantumCircuit(width)
            circuit.x(wire)
            cases.append((circuit, local(x, width, wire)))
            circuit = QuantumCircuit(width)
            circuit.h(wire)
            circuit.s(wire)
            cases.append((circuit, local(s @ h, width, wire)))
        if width > 1:
            for control, target in ((0, width - 1), (width - 1, 0)):
                circuit = QuantumCircuit(width)
                circuit.h(control)
                circuit.cx(control, target)
                cases.append((circuit, cx(width, control, target) @ local(h, width, control)))
        circuit = QuantumCircuit(width)
        circuit.u(0.39702, 0.238798, 0.298374, 0)
        expected = local(u(0.39702, 0.238798, 0.298374), width, 0)
        if width > 1:
            circuit.cx(0, width - 1)
            expected = cx(width, 0, width - 1) @ expected
        circuit.global_phase = 0.271
        cases.append((circuit, np.exp(0.271j) * expected))
        parameter = Parameter('angle')
        circuit = QuantumCircuit(width)
        circuit.rx(parameter, width - 1)
        circuit = circuit.assign_parameters({parameter: -0.37})
        rotation = np.cos(-0.37 / 2) * np.eye(2) - 1j * np.sin(-0.37 / 2) * x
        cases.append((circuit, local(rotation, width, width - 1)))

    first, second = QuantumRegister(1, 'first'), QuantumRegister(2, 'second')
    circuit = QuantumCircuit(second, first)
    circuit.h(first[0])
    circuit.s(second[0])
    circuit.cx(first[0], second[0])
    cases.append((circuit, cx(3, 2, 0) @ local(s, 3, 0) @ local(h, 3, 2)))
    inner = QuantumCircuit(2)
    inner.h(1)
    inner.s(1)
    inner.cx(1, 0)
    inner.global_phase = -0.19
    supplied = Gate('supplied', 2, [])
    supplied.definition = inner
    outer = QuantumCircuit(2)
    outer.append(supplied, [1, 0])
    outer.global_phase = 0.43
    cases.append((outer, np.exp(0.24j) * cx(2, 0, 1) @ local(s @ h, 2, 0)))

    return tuple(cases)
"""

CHECK = (
    CASE_FACTORY
    + """
def check(candidate):
    import numpy as np
    from qiskit.quantum_info import Statevector

    for circuit, operator in statevector_cases():
        # Freeze original amplitudes before permitting candidate input mutation.
        wanted = operator[:, 0].copy()
        width = circuit.num_qubits
        state = candidate(circuit)
        assert isinstance(state, Statevector), 'Expected a Statevector value'
        assert state.dims() == (2,) * width, 'Incorrect subsystem dimensions'
        actual = np.asarray(state.data)
        assert actual.shape == wanted.shape, 'Incorrect amplitude shape'
        assert np.isfinite(actual).all(), 'Nonfinite amplitudes'
        # Unit state amplitudes cannot exceed one; bound before phase arithmetic.
        assert (np.abs(actual.real) <= 1 + 1e-10).all(), 'Invalid real amplitudes'
        assert (np.abs(actual.imag) <= 1 + 1e-10).all(), 'Invalid imaginary amplitudes'
        index = int(np.argmax(np.abs(wanted)))
        phase = actual[index] / wanted[index]
        assert abs(phase) > 0, 'Missing state amplitude'
        phase /= abs(phase)
        assert np.allclose(actual, phase * wanted, atol=1e-10, rtol=0), 'Incorrect state action'
"""
)


def revised_task(task):
    suite = task.public.suite
    if suite not in SOURCE_RECORDS:
        raise ValueError("Expected the exact pinned Task 11 source")
    pinned = SOURCE_RECORDS[suite]
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": pinned["prompt"]}),
            "upstream_test": pinned["test"],
        }
    )
    if source.digest != pinned["digest"]:
        raise ValueError("Expected the exact pinned Task 11 source")
    prompt = (
        "from qiskit import QuantumCircuit\nfrom qiskit.quantum_info import Statevector\n"
        "def get_statevector(circuit: QuantumCircuit) -> Statevector:\n"
        + '    """'
        + REQUIREMENT
        + '"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement get_statevector(circuit) in Python."
    )
    revised = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": CHECK,
        }
    )
    if task.digest not in (source.digest, revised.digest):
        raise ValueError("Expected the exact pinned Task 11 source or its exact revision")
    return revised


class StatevectorActionJudge:
    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("Task 11 requires graph protocol 4")
        if kwargs.pop("graph_transport", "delta-v1") != "delta-v1":
            raise ValueError("Task 11 requires delta graph transport")
        if kwargs.pop("graph_batch", "none") != "none":
            raise ValueError("Task 11 requires individual calls")
        kwargs.setdefault("output_limit", 16 * 1024 * 1024)
        limits = GraphLimits(message_bytes=kwargs["output_limit"], depth=128)
        if kwargs.pop("graph_limits", limits) != limits:
            raise ValueError("Task 11 requires its frozen graph bounds")
        self.inner = UpstreamJudge(
            protocol=4, graph_transport="delta-v1", graph_limits=limits, **kwargs
        )

    def revise(self, task):
        return revised_task(task)

    def configuration(self, task):
        if task.digest != revised_task(task).digest:
            raise ValueError("Revise Task 11 before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": TRACK,
            "source": source_manifest(),
            "source_task_digest": SOURCE_RECORDS[task.public.suite]["digest"],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract_digest": task.public.digest,
            "public_contract": REQUIREMENT,
            "input_mutation": "permitted; original amplitudes frozen before dispatch",
            "runtime_qualification": "unqualified; complete valid controls must pass",
            "release_eligible": False,
            "inner": inner,
            "limitations": [
                "43 authored circuits do not exhaust the declared input domain",
                "Graph values do not attest native object provenance or simulation methods",
                "Statevector extraction depends on the pinned Qiskit runtime",
                "Isolated controls, resource calibration and independent admission are pending",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

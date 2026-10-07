"""Source-bound matrix semantics; construction methods are not attested."""

from graybench.gate_semantics import (
    DIAGONAL_CHECK,
    DIAGONAL_CONTRACT,
    EVOLUTION_CHECK,
    EVOLUTION_CONTRACT,
)
from graybench.graph_limits import GraphLimits
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.matrix_task_sources import SOURCE_RECORDS
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

GATE_CONTRACT = (
    "Given a numeric unitary QuantumCircuit on at least one qubit with no classical "
    "bits or unbound parameters, return a Qiskit Gate on exactly those qubits and no "
    "classical bits, equivalent to the input circuit in Qiskit's computational-basis "
    "order. Gate subclasses and equivalent constructions are allowed. An overall "
    "unit-modulus global phase is allowed. Matrix entries after phase alignment use "
    "absolute tolerance 1e-10 and zero relative tolerance. The input may be modified, "
    "but the result must implement its original action. Internal conversion methods "
    "and native object provenance are not attested."
)

GATE_CHECK = """def check(candidate):
    import numpy as np
    from qiskit import QuantumCircuit, QuantumRegister
    from qiskit.circuit import Gate, Parameter
    from qiskit.exceptions import QiskitError
    from qiskit.quantum_info import Operator

    x = np.array([[0,1],[1,0]], dtype=complex)
    h = np.array([[1,1],[1,-1]], dtype=complex) / np.sqrt(2)
    z = np.diag([1,-1]).astype(complex)
    s = np.diag([1,1j])
    cases = []

    def local(matrix, width, wire):
        result = np.ones((1,1), dtype=complex)
        for index in reversed(range(width)):
            result = np.kron(result, matrix if index == wire else np.eye(2))
        return result

    def cx(width, control, target):
        result = np.zeros((2**width,2**width), dtype=complex)
        for column in range(2**width):
            row = column ^ (1<<target) if column & (1<<control) else column
            result[row,column] = 1
        return result

    for width in range(1,5):
        cases.append((QuantumCircuit(width), np.eye(2**width, dtype=complex)))
        for wire in sorted({0, width-1}):
            circuit = QuantumCircuit(width)
            circuit.h(wire)
            circuit.x(wire)
            circuit.h(wire)
            cases.append((circuit, local(z,width,wire)))
        circuit = QuantumCircuit(width)
        circuit.h(0)
        circuit.s(width-1)
        expected = local(s,width,width-1) @ local(h,width,0)
        if width > 1:
            circuit.cx(0,width-1)
            circuit.cx(width-1,0)
            expected = cx(width,width-1,0) @ cx(width,0,width-1) @ expected
        circuit.global_phase = 0.271
        cases.append((circuit, np.exp(0.271j) * expected))

    parameter = Parameter('angle')
    circuit = QuantumCircuit(1)
    circuit.rx(parameter,0)
    circuit = circuit.assign_parameters({parameter:-0.37})
    cases.append((circuit, np.cos(-0.37/2)*np.eye(2) - 1j*np.sin(-0.37/2)*x))

    first, second = QuantumRegister(1,'first'), QuantumRegister(2,'second')
    circuit = QuantumCircuit(second,first)
    circuit.h(first[0])
    circuit.cx(first[0],second[0])
    cases.append((circuit, cx(3,2,0) @ local(h,3,2)))

    inner = QuantumCircuit(2)
    inner.h(1)
    inner.cx(1,0)
    inner.global_phase = -0.19
    supplied = Gate('supplied',2,[])
    supplied.definition = inner
    outer = QuantumCircuit(2)
    outer.append(supplied,[1,0])
    outer.global_phase = 0.43
    cases.append((outer, np.exp(0.24j) * (cx(2,0,1) @ local(h,2,0))))

    for circuit, expected in cases:
        # Freeze the original action independently before allowing candidate mutation.
        wanted = expected.copy()
        width = circuit.num_qubits
        gate = candidate(circuit)
        assert isinstance(gate, Gate), 'Expected a Gate value'
        assert gate.num_qubits == width and gate.num_clbits == 0, 'Incorrect gate width'
        assert not gate.is_parameterized(), 'Unbound gate parameters'
        try:
            actual = np.asarray(Operator(gate).data)
        except (QiskitError, ValueError, TypeError) as exc:
            raise AssertionError('Gate does not define an operator') from exc
        assert actual.shape == wanted.shape, 'Incorrect operator shape'
        assert np.isfinite(actual).all(), 'Nonfinite gate matrix'
        index = np.unravel_index(np.argmax(np.abs(wanted)),wanted.shape)
        phase = actual[index] / wanted[index]
        assert abs(phase) > 0, 'Missing operator entry'
        phase /= abs(phase)
        assert np.allclose(actual,phase*wanted,atol=1e-10,rtol=0), 'Incorrect gate action'
"""

REVISIONS = {
    "qhe116-evolution-graph-v2": (
        116,
        "synthesize_evolution_gate",
        "pauli_string, time",
        EVOLUTION_CONTRACT.replace("time is real", "time is finite and real"),
        EVOLUTION_CHECK,
    ),
    "qhe120-diagonal-graph-v2": (
        120,
        "create_diagonal_circuit",
        "diag",
        DIAGONAL_CONTRACT.replace(
            "Do not mutate diag.",
            "Inputs may be modified, but results must describe their original values.",
        ),
        DIAGONAL_CHECK,
    ),
    "qhe125-gate-action-graph-v1": (125, "circ_to_gate", "circ", GATE_CONTRACT, GATE_CHECK),
}


def revised_task(task, track):
    number, entry, arguments, requirement, check = REVISIONS[track]
    suite = task.public.suite
    if (
        suite not in ("normal", "hard")
        or task.public.task_id != f"qiskitHumanEval/{number}"
        or task.public.family_id != f"qhe/{number}"
        or task.public.entry_point != entry
        or task.public.prompt_format
        != ("function_completion" if suite == "normal" else "standalone_function")
    ):
        raise ValueError("Expected the exact pinned matrix task source")
    pinned = SOURCE_RECORDS[number, suite]
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": pinned["prompt"]}),
            "upstream_test": pinned["test"],
        }
    )
    if source.digest != pinned["digest"]:
        raise ValueError("Expected the exact pinned matrix task source")
    prompt = (
        "from qiskit import QuantumCircuit\n"
        + f"def {entry}({arguments}):\n"
        + '    """'
        + requirement
        + '"""\n'
        if suite == "normal"
        else requirement + f" Implement {entry}({arguments}) in Python."
    )
    revised = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": check,
        }
    )
    if task.digest not in (source.digest, revised.digest):
        raise ValueError("Expected the exact pinned source or its exact matrix revision")
    return revised


class CircuitMatrixJudge:
    def __init__(self, track, **kwargs):
        if track not in REVISIONS:
            raise ValueError("Unknown matrix semantics condition")
        self.track = track
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("Matrix condition requires graph protocol 4")
        if kwargs.pop("graph_transport", "delta-v1") != "delta-v1":
            raise ValueError("Matrix condition requires delta graph transport")
        if kwargs.pop("graph_batch", "none") != "none":
            raise ValueError("Matrix condition requires individual calls")
        kwargs.setdefault("output_limit", 16 * 1024 * 1024)
        limits = GraphLimits(message_bytes=kwargs["output_limit"], depth=128)
        if kwargs.pop("graph_limits", limits) != limits:
            raise ValueError("Matrix condition requires its frozen resource bounds")
        self.inner = UpstreamJudge(
            protocol=4, graph_transport="delta-v1", graph_limits=limits, **kwargs
        )

    def revise(self, task):
        return revised_task(task, self.track)

    def configuration(self, task):
        if task.digest != self.revise(task).digest:
            raise ValueError("Revise the matrix task before generation and judgment")
        payload, inner = self.inner.configuration(task)
        number, _, _, requirement, _ = REVISIONS[self.track]
        return payload, {
            "track": self.track,
            "source": source_manifest(),
            "release_eligible": False,
            "source_task_digest": SOURCE_RECORDS[number, task.public.suite]["digest"],
            "public_contract_digest": task.public.digest,
            "task_digest": task.digest,
            "public_contract": requirement,
            "input_mutation": "permitted; original expectations frozen before dispatch",
            "runtime_qualification": "unqualified; complete valid controls must pass",
            "inner": inner,
            "limitations": [
                "Finite authored inputs do not exhaust the declared public domain",
                "Construction methods and native object provenance are not attested",
                "Output extraction depends on the pinned Qiskit Operator runtime",
                "Some valid matrix representations require qualified registered-native storage",
                "Isolated controls, resource calibration and independent admission are pending",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

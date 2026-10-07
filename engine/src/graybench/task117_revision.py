"""Exact-ancestry, input-sensitive two-qubit unitary development condition."""

from graybench.datasets import JudgeTask
from graybench.graph_limits import GraphLimits
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

TRACK = "qhe117-unitary-basis-graph-v1"
NESTED_TRACK = "qhe117-unitary-basis-graph-v2"
SOURCE_DIGESTS = {
    "normal": "371457d27064cad6b3ae9890a2dec222b21ed1504b71cffea37338d46582a635",
    "hard": "5592fbd731478c12c3e870d4daef0ecf88f4d873e2f17c72d196b5f2afb66a07",
}
IMPORTS = (
    "from qiskit.synthesis import TwoQubitBasisDecomposer\n"
    "from qiskit.quantum_info import Operator, random_unitary\n"
    "from qiskit.circuit.library import CXGate\n"
    "from qiskit import QuantumCircuit\nimport numpy as np\n"
)
REQUIREMENT = (
    "Given a finite 4x4 unitary as a Qiskit Operator on two qubits, return a "
    "two-qubit QuantumCircuit representing that operator in the same qubit "
    "order, up to global phase. Absolute tolerance is 1e-8 and relative "
    "tolerance is 1e-10. The expanded circuit must consist of numeric "
    "single-qubit unitary gates and CX gates in either orientation and with "
    "either open or closed control; barriers "
    "are allowed. Explicit composite Gate objects with finite circuit "
    "definitions are allowed and assessed by recursively expanding those "
    "definitions, up to 16 circuit levels. Other multi-qubit primitives, "
    "including opaque UnitaryGate matrix instructions, are not a CX-basis "
    "decomposition; the judge will not synthesize them. Measurements, resets, "
    "classical controls, control flow, timing "
    "instructions and unbound parameters are not allowed. Unused classical "
    "bits, circuit metadata, names and labels are not scored. Identity and "
    "local operators need not contain CX gates, and gate count or minimality "
    "is not scored. The input may be modified, but the result must represent "
    "its original value. This is a return-value and expanded-basis contract; "
    "equivalent synthesis methods are accepted, and an internal call to "
    "TwoQubitBasisDecomposer or native object provenance is not attested."
)
CHECK = """def check(candidate):
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.circuit import Gate
    from qiskit.circuit.library import Barrier, CXGate
    from qiskit.quantum_info import Operator

    # Qiskit orders the first instruction qubit as the least significant bit.
    cx = np.array([[1,0,0,0],[0,0,0,1],[0,0,1,0],[0,1,0,0]], dtype=complex)

    def lift(small, positions):
        expanded = np.zeros((4,4), dtype=complex)
        mask = sum(1 << p for p in positions)
        for col in range(4):
            local_col = sum(((col >> p) & 1) << k for k,p in enumerate(positions))
            for local_row in range(2**len(positions)):
                row = (col & ~mask) | sum(
                    ((local_row >> k) & 1) << p for k,p in enumerate(positions)
                )
                expanded[row,col] = small[local_row,local_col]
        return expanded

    def expanded_operator(circuit, positions=(0,1), depth=0):
        assert depth < 16, 'Circuit definition depth exceeds the declared limit'
        assert not circuit.parameters, 'Unbound circuit parameters'
        phase = float(circuit.global_phase)
        assert np.isfinite(phase), 'Nonfinite global phase'
        value = np.exp(1j*phase) * np.eye(4, dtype=complex)
        for item in circuit.data:
            operation = item.operation
            assert not item.clbits and not operation.num_clbits, 'Classical operation'
            assert getattr(operation, 'condition', None) is None, 'Classical control'
            wires = tuple(positions[circuit.find_bit(q).index] for q in item.qubits)
            if isinstance(operation, Barrier):
                continue
            assert isinstance(operation, Gate), 'Expected unitary gates or barriers'
            if operation.base_class is Gate:
                definition = operation.definition
                assert isinstance(definition, QuantumCircuit), 'Missing CX-basis definition'
                assert definition.num_qubits == len(wires), 'Invalid gate definition width'
                step = expanded_operator(definition, wires, depth+1)
            elif operation.num_qubits == 1:
                small = np.asarray(Operator(operation).data, dtype=complex)
                assert small.shape == (2,2) and np.isfinite(small).all(), 'Invalid local gate'
                assert np.allclose(small.conj().T @ small, np.eye(2),
                                   atol=1e-8, rtol=1e-10), 'Nonunitary local gate'
                step = lift(small, wires)
            elif isinstance(operation, CXGate):
                assert operation.ctrl_state in (0,1), 'Invalid CX control state'
                if operation.ctrl_state == 0:
                    flip = np.eye(4)[:,[1,0,3,2]]
                    step = lift(flip @ cx @ flip, wires)
                else:
                    step = lift(cx, wires)
            else:
                raise AssertionError('Expected CX or an explicit composite Gate')
            value = step @ value
        return value

    eye = np.eye(4, dtype=complex)
    h = np.array([[1,1],[1,-1]], dtype=complex) / np.sqrt(2)
    s = np.diag([1,1j])
    rx = np.array([[np.cos(0.23),-1j*np.sin(0.23)],
                   [-1j*np.sin(0.23),np.cos(0.23)]])
    swap = eye[:,[0,2,1,3]]
    reverse_cx = swap @ cx @ swap
    inputs = [eye, np.exp(0.37j)*eye, cx, reverse_cx, swap,
              np.kron(h,np.eye(2)), np.kron(np.eye(2),h), np.kron(s,rx),
              np.diag([1,1,1,np.exp(0.71j)])]
    for seed in (19,23,31,47,53,67):
        rng = np.random.default_rng(seed)
        dense = rng.normal(size=(4,4)) + 1j*rng.normal(size=(4,4))
        inputs.append(np.linalg.qr(dense)[0])
    for template in inputs:
        expected = template.copy()  # Freeze before allowing input mutation.
        actual = candidate(Operator(template.copy()))
        assert isinstance(actual, QuantumCircuit), 'Expected a QuantumCircuit'
        assert actual.num_qubits == 2, 'Expected exactly two qubits'
        matrix = expanded_operator(actual)
        assert np.isfinite(matrix).all(), 'Nonfinite circuit operator'
        assert np.allclose(matrix.conj().T @ matrix, eye,
                           atol=1e-8, rtol=1e-10), 'Nonunitary circuit operator'
        pivot = np.unravel_index(np.argmax(np.abs(expected)), expected.shape)
        phase = matrix[pivot] / expected[pivot]
        assert np.isfinite(phase) and abs(phase) > 0, 'Invalid phase comparison'
        phase /= abs(phase)
        assert np.allclose(matrix, phase*expected, atol=1e-8, rtol=1e-10), (
            'Returned circuit does not represent the supplied unitary'
        )
"""
PINNED_DESCRIPTION = (
    "Decompose a 4x4 unitary using the TwoQubitBasisDecomposer with CXGate as the basis gate.\n"
)
PINNED_PROMPTS = {
    "normal": IMPORTS
    + "def decompose_unitary(unitary: Operator) -> QuantumCircuit:\n"
    + '    """ '
    + PINNED_DESCRIPTION
    + '    Return the resulting QuantumCircuit.\n    """',
    "hard": PINNED_DESCRIPTION + "Return the resulting QuantumCircuit.\n"
    "You must implement this using a function named `decompose_unitary` "
    "with the following arguments: unitary.",
}
PINNED_CHECK = (
    """def check(candidate):
    unitary = random_unitary(4)
    try:
        qc = candidate(unitary)
"""
    + (
        '        assert isinstance(qc, QuantumCircuit), f"Expected QuantumCircuit instance, '
        'got {type(qc).__name__}"\n'
    )
    + """\
        assert qc.num_qubits == 2, f"Expected 2 qubits, got {qc.num_qubits}"
        assert qc.size() > 0, f"Expected size > 0, got {qc.size()}"

        cx_count = sum(1 for inst in qc.data if inst.operation.name == "cx")
        assert cx_count > 0, f"Expected {cx_count} > 0"
    except (ValueError, np.linalg.LinAlgError) as e:
        raise e
"""
)


def revised_task(task: JudgeTask) -> JudgeTask:
    suite = task.public.suite
    if suite not in SOURCE_DIGESTS:
        raise ValueError("Expected the exact pinned QHE task-117 source")
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": PINNED_PROMPTS[suite]}),
            "upstream_test": PINNED_CHECK
            if suite == "normal"
            else IMPORTS + PINNED_CHECK + "\ncheck(decompose_unitary)",
        }
    )
    if source.digest != SOURCE_DIGESTS[suite]:
        raise ValueError("Expected the exact pinned QHE task-117 source")
    prompt = (
        IMPORTS
        + "def decompose_unitary(unitary: Operator) -> QuantumCircuit:\n"
        + '    """'
        + REQUIREMENT
        + '"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement decompose_unitary(unitary) in Python."
    )
    revised = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": CHECK,
        }
    )
    if task.digest not in (source.digest, revised.digest):
        raise ValueError("Expected the exact pinned QHE task-117 source or its exact revision")
    return revised


class UnitaryBasisJudge:
    def __init__(self, *, track=TRACK, **kwargs):
        if track not in (TRACK, NESTED_TRACK):
            raise ValueError("Unknown task 117 resource condition")
        self.track = track
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("Task 117 revision requires graph protocol 4")
        if kwargs.pop("graph_transport", "delta-v1") != "delta-v1":
            raise ValueError("Task 117 revision requires delta graph transport")
        if kwargs.pop("graph_batch", "none") != "none":
            raise ValueError("Task 117 revision requires individual calls")
        kwargs.setdefault("output_limit", 16 * 1024 * 1024)
        if track == NESTED_TRACK:
            limits = GraphLimits(message_bytes=kwargs["output_limit"], depth=128)
            if kwargs.pop("graph_limits", limits) != limits:
                raise ValueError("Task 117 v2 requires its frozen graph resource bounds")
            kwargs["graph_limits"] = limits
        elif (
            isinstance(kwargs.get("graph_limits"), GraphLimits)
            and kwargs["graph_limits"].depth > 32
        ):
            raise ValueError("Task 117 v1 retains its historical graph depth ceiling")
        self.inner = UpstreamJudge(protocol=4, graph_transport="delta-v1", **kwargs)

    def revise(self, task):
        return revised_task(task)

    def configuration(self, task):
        if task.digest != revised_task(task).digest:
            raise ValueError("Revise task 117 before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": self.track,
            "release_eligible": False,
            "source": source_manifest(),
            "pinned_source_task_digest": SOURCE_DIGESTS[task.public.suite],
            "source_task_digest": SOURCE_DIGESTS[task.public.suite],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract_digest": task.public.digest,
            "public_contract": REQUIREMENT,
            "input_mutation": "permitted; expected operator frozen before dispatch",
            "inner": inner,
            "limitations": [
                "15 authored inputs do not exhaust the unitary domain",
                "Expanded-basis semantics do not attest an internal synthesis routine",
                "Graph output cannot attest native object provenance",
                "Independent task admission and isolated control verification are pending",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome,
            identity(manifest),
            {"manifest": manifest, "inner": result.evidence},
        )

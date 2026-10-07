"""Explicit symmetric W-state preparation and terminal measurement condition."""

from graybench.graph_limits import GraphLimits
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.task66_sources import SOURCE_RECORDS
from graybench.upstream import UpstreamJudge

TRACK = "qhe66-symmetric-w-measurement-graph-v1"
REQUIREMENT = (
    "Return a plain Qiskit QuantumCircuit on exactly three qubits that, starting "
    "in |000>, prepares the symmetric state (|001> + |010> + |100>)/sqrt(3) and "
    "then measures each qubit exactly once in the computational basis. Basis "
    "order is |q2 q1 q0>. An overall global phase is allowed; relative phases "
    "must give the specified state. The pre-measurement density matrix is compared "
    "entrywise at absolute tolerance 1e-10 and zero relative tolerance. Each qubit "
    "must be measured into a distinct classical bit; measurement order, bit "
    "mapping and register names are unrestricted. There may be three to 64 "
    "classical bits, including unused bits. No preparation operation may occur "
    "after the first measurement. Barriers are allowed anywhere. Numeric unitary "
    "Gate operations, resets and Initialize are allowed before measurement. "
    "Unitary gate matrices use the same absolute tolerance and zero relative "
    "tolerance. Generic Gate, Instruction and ControlledGate circuit definitions "
    "made of these operations are expanded, including nested final measurements. "
    "At most 16 active effective composite definition levels below the returned "
    "circuit and 1024 visited instruction entries, including composite entries, "
    "are allowed. For generic ControlledGate, the effective definition includes "
    "Qiskit's open-control X wrappers, which count toward these bounds. Registered "
    "SDK operations are evaluated as primitives; their internal synthesis "
    "definitions are not counted. Classical control, "
    "control flow, delays, unbound parameters, other quantum channels and "
    "nonfinite parameters or matrices are not allowed. Any correct preparation "
    "method is accepted; a particular constructor, gate sequence, minimality, "
    "sampling execution and native object provenance are not attested. Circuit "
    "names, labels and metadata are not scored. This graph condition uses the "
    "registered data-only Qiskit representation with a 16 MiB message/state limit, "
    "100000 nodes/edges, 512 KiB array/matrix limits and graph depth 128; unsupported "
    "representations remain separately labeled, without a value-copy fallback."
)

CHECK = """def assert_w_density(data):
    import numpy as np
    assert type(data) is np.ndarray and data.shape == (8,8), 'Incorrect density shape'
    assert np.isfinite(data).all(), 'Nonfinite density matrix'
    wanted = np.zeros((8,8), dtype=complex)
    for row in (1,2,4):
        for column in (1,2,4):
            wanted[row,column] = 1/3
    assert np.allclose(data, wanted, atol=1e-10, rtol=0), 'Incorrect symmetric W state'

def check(candidate):
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.circuit import Barrier, ControlledGate, Gate, Instruction, Measure, Reset
    from qiskit.circuit.library import Initialize
    from qiskit.exceptions import QiskitError
    from qiskit.quantum_info import DensityMatrix, Operator

    circuit = candidate()
    assert type(circuit) is QuantumCircuit, 'Expected a plain QuantumCircuit'
    assert circuit.num_qubits == 3, 'Expected three qubits'
    assert 3 <= circuit.num_clbits <= 64, 'Classical bit count outside declared bounds'
    flattened = []
    visited = 0

    def expand(body, qmap, cmap, depth=0):
        nonlocal visited
        assert depth <= 16, 'Circuit definition depth exceeds declared bound'
        assert type(body) is QuantumCircuit, 'Invalid circuit definition'
        assert not body.parameters, 'Unbound parameters'
        assert np.isfinite(float(body.global_phase)), 'Nonfinite global phase'
        for item in body.data:
            visited += 1
            assert visited <= 1024, 'Instruction expansion exceeds declared bound'
            operation = item.operation
            assert isinstance(operation, Instruction), 'Invalid preparation instruction'
            assert getattr(operation, 'condition', None) is None, 'Classical control'
            wires = tuple(qmap[body.find_bit(bit).index] for bit in item.qubits)
            bits = tuple(cmap[body.find_bit(bit).index] for bit in item.clbits)
            assert len(wires) == operation.num_qubits and len(set(wires)) == len(wires), (
                'Invalid preparation qubit operands'
            )
            assert len(bits) == operation.num_clbits, 'Invalid Classical operands'
            assert not operation.is_parameterized(), 'Unbound instruction parameters'
            for parameter in operation.params:
                if isinstance(parameter, (float, complex, np.number, np.ndarray)):
                    assert np.isfinite(parameter).all(), 'Nonfinite instruction parameter'
            if operation.base_class in (Gate, Instruction, ControlledGate):
                definition = operation.definition
                assert type(definition) is QuantumCircuit, 'Missing preparation definition'
                assert definition.num_qubits == len(wires), 'Definition qubit width differs'
                assert definition.num_clbits == len(bits), 'Definition Classical width differs'
                expand(definition, wires, bits, depth+1)
            else:
                assert isinstance(operation, (Gate, Reset, Initialize, Barrier, Measure)), (
                    'Unsupported preparation operation'
                )
                if isinstance(operation, Measure):
                    assert len(wires) == len(bits) == 1, 'Invalid measurement operands'
                else:
                    assert not bits and not operation.num_clbits, 'Classical preparation operation'
                flattened.append((operation, wires, bits))

    expand(circuit, (0,1,2), tuple(range(circuit.num_clbits)))
    preparation = QuantumCircuit(3)
    measurements = []
    for operation, wires, bits in flattened:
        if isinstance(operation, Barrier):
            continue
        if isinstance(operation, Measure):
            measurements.append((wires[0],bits[0]))
            continue
        assert not measurements, 'Preparation after first measurement'
        try:
            if isinstance(operation, Gate):
                matrix = np.asarray(Operator(operation).data)
                width = 2**len(wires)
                assert matrix.shape == (width,width), 'Incorrect preparation gate shape'
                assert np.isfinite(matrix).all(), 'Nonfinite preparation gate'
                assert (np.abs(matrix.real) <= 1+1e-10).all(), 'Invalid preparation gate entries'
                assert (np.abs(matrix.imag) <= 1+1e-10).all(), 'Invalid preparation gate entries'
                assert np.allclose(matrix.conj().T @ matrix, np.eye(width),
                                   atol=1e-10, rtol=0), 'Nonunitary preparation gate'
            preparation.append(operation, wires)
        except (QiskitError, ValueError, TypeError, FloatingPointError) as error:
            raise AssertionError('Invalid preparation operation') from error
    assert len(measurements) == 3, 'Expected three final measurements'
    assert {wire for wire, _ in measurements} == {0,1,2}, 'Measured qubits differ'
    assert len({bit for _, bit in measurements}) == 3, 'Classical measurement bits reused'
    try:
        data = DensityMatrix.from_instruction(preparation).data
    except (QiskitError, ValueError, TypeError, FloatingPointError) as error:
        raise AssertionError('Invalid preparation evolution') from error
    assert_w_density(data)
"""


def revised_task(task):
    suite = task.public.suite
    if suite not in SOURCE_RECORDS:
        raise ValueError("Expected the exact pinned Task66 source")
    pinned = SOURCE_RECORDS[suite]
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": pinned["prompt"]}),
            "upstream_test": pinned["test"],
        }
    )
    if source.digest != pinned["digest"]:
        raise ValueError("Expected the exact pinned Task66 source")
    prompt = (
        "from qiskit import QuantumCircuit\nfrom numpy import arccos, sqrt\n"
        "def w_state()->QuantumCircuit:\n    " + '"""' + REQUIREMENT + '"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement w_state() with no arguments in Python."
    )
    revision = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": CHECK,
        }
    )
    if task.digest not in (source.digest, revision.digest):
        raise ValueError("Expected the exact pinned Task66 source or its exact revision")
    return revision


class WMeasurementJudge:
    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("Task66 requires graph protocol 4")
        if kwargs.pop("graph_transport", "delta-v1") != "delta-v1":
            raise ValueError("Task66 requires delta graph transport")
        if kwargs.pop("graph_batch", "none") != "none":
            raise ValueError("Task66 requires individual calls")
        limit = 16 * 1024 * 1024
        if kwargs.pop("output_limit", limit) != limit:
            raise ValueError("Task66 requires its frozen output limit")
        if kwargs.pop("graph_state_limit", None) not in (None, limit):
            raise ValueError("Task66 requires its frozen state limit")
        limits = GraphLimits(message_bytes=limit, depth=128)
        if kwargs.pop("graph_limits", limits) != limits:
            raise ValueError("Task66 requires its frozen graph bounds")
        self.inner = UpstreamJudge(
            protocol=4,
            graph_transport="delta-v1",
            output_limit=limit,
            graph_state_limit=limit,
            graph_limits=limits,
            **kwargs,
        )

    def revise(self, task):
        return revised_task(task)

    def configuration(self, task):
        if task.digest != revised_task(task).digest:
            raise ValueError("Revise Task66 before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": TRACK,
            "source": source_manifest(),
            "source_task_digest": SOURCE_RECORDS[task.public.suite]["digest"],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract_digest": task.public.digest,
            "public_contract": REQUIREMENT,
            "calls": 1,
            "oracle": "Independent symmetric W density entries; separate expanded measurement map",
            "sampling": "None; circuit state and structure only",
            "runtime_qualification": "unqualified; isolated valid/invalid controls must pass",
            "release_eligible": False,
            "inner": inner,
            "limitations": [
                "Width/phase/measurement/resource choices are declared before generation",
                "Evolution and gate unitarity depend on the pinned SDK and decoded graph",
                "Native object identity, constructor use and sampling execution are not attested",
                "Encoder integrity, isolated resources and human admission remain pending",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

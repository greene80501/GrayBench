import os

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Barrier

from graybench.circuit_wire import WireError
from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.graph_wire import GraphArena, GraphLimits
from graybench.upstream import UpstreamJudge


def transfer(sender, receiver, value, sequence=1):
    wire = sender.snapshot({"value": value}, sequence=sequence)
    return receiver.commit(receiver.prepare(wire, sequence=sequence))["value"]


def test_barrier_identity_and_separate_native_label_caches():
    sender, receiver = (
        GraphArena(side=side, session="barrier", limits=GraphLimits())
        for side in ("judge", "candidate")
    )
    barrier = Barrier(2, label="first")
    first, second = QuantumCircuit(2), QuantumCircuit(2)
    first.append(barrier, [0, 1], copy=False)
    barrier.label = "second"
    second.append(barrier, [0, 1], copy=False)
    barrier.label = "current"
    a, b, remote, attrs, params = transfer(
        sender, receiver, (first, second, barrier, vars(barrier), barrier.params)
    )
    assert type(remote) is Barrier and vars(remote) is attrs and remote.params is params
    assert a.data[0].operation is b.data[0].operation is remote
    assert (a.data[0].label, b.data[0].label, remote.label) == ("first", "second", "current")
    remote.label = "returned"
    assert transfer(receiver, sender, remote) is barrier
    assert barrier.label == "returned" and first.data[0].label == "first"
    assert type(barrier.inverse()) is Barrier and barrier._definition is None


def test_packed_barrier_keeps_fresh_wrappers_and_detached_wrapper_state():
    from qiskit.converters import circuit_to_dag, dag_to_circuit

    sender, receiver = (
        GraphArena(side=side, session="packed-barrier", limits=GraphLimits())
        for side in ("judge", "candidate")
    )
    original = QuantumCircuit(2)
    original.barrier(label="packed")
    circuit = dag_to_circuit(circuit_to_dag(original))
    wrapper = circuit.data[0].operation
    assert wrapper is not circuit.data[0].operation
    wrapper.label = "detached"
    remote, held = transfer(sender, receiver, (circuit, wrapper))
    assert remote.data[0].operation is not remote.data[0].operation
    assert remote.data[0].operation is not held
    assert remote.data[0].label == remote.data[0].operation.label == "packed"
    assert held.label == "detached"
    held.label = "returned"
    assert transfer(receiver, sender, remote) is circuit
    assert wrapper.label == "returned" and circuit.data[0].operation.label == "packed"


@pytest.mark.parametrize("width", [0, 1, 3])
def test_packed_barrier_native_width_and_operand_order(width):
    from qiskit.converters import circuit_to_dag, dag_to_circuit

    sender, receiver = (
        GraphArena(side=side, session="barrier-width", limits=GraphLimits())
        for side in ("judge", "candidate")
    )
    circuit = QuantumCircuit(width)
    circuit.barrier(*reversed(range(width)), label="λ")
    circuit = dag_to_circuit(circuit_to_dag(circuit))
    remote = transfer(sender, receiver, circuit)
    assert remote.data[0].operation.num_qubits == width
    assert remote.data[0].qubits == tuple(reversed(remote.qubits))
    assert remote.data[0].label == "λ"
    assert remote.data[0].operation is not remote.data[0].operation


@pytest.mark.parametrize(
    "field,value", [("directive", "unknown"), ("num_qubits", -1), ("qubits", [8])]
)
def test_malformed_packed_barrier_rejected_before_mutation(field, value):
    from qiskit.converters import circuit_to_dag, dag_to_circuit

    sender, receiver = (
        GraphArena(side=side, session="barrier-validation", limits=GraphLimits())
        for side in ("judge", "candidate")
    )
    circuit = QuantumCircuit(2)
    circuit.barrier(label="before")
    circuit = dag_to_circuit(circuit_to_dag(circuit))
    remote = transfer(sender, receiver, circuit)
    circuit.metadata["changed"] = True
    wire = sender.snapshot({"value": circuit}, sequence=2)
    record = next(item for item in wire["nodes"] if item["kind"] == "circuit_data")
    record["state"]["operations"][0][field] = value
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=2)
    assert remote.metadata == {} and remote.data[0].label == "before"


def test_compiled_ansatz_retains_parameters_and_packed_barriers():
    from qiskit.circuit.library import efficient_su2

    sender, receiver = (
        GraphArena(side=side, session="barrier-ansatz", limits=GraphLimits())
        for side in ("judge", "candidate")
    )
    circuit = efficient_su2(3, reps=1, insert_barriers=True)
    remote = transfer(sender, receiver, circuit)
    assert remote == circuit and remote.num_parameters == circuit.num_parameters
    indices = [i for i, item in enumerate(remote.data) if item.name == "barrier"]
    assert len(indices) == 2
    for i in indices:
        assert remote.data[i].operation is not remote.data[i].operation


@pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires pinned Docker image"
)
def test_protected_measure_all_preserves_barrier_and_input_mutation():
    code = """def answer(qc):
    qc.measure_all()
    return qc
"""
    test = """from qiskit import QuantumCircuit
from qiskit.circuit import Barrier
def check(candidate):
    qc = QuantumCircuit(2)
    qc.x(0)
    held = qc.metadata
    assert candidate(qc) is qc
    assert qc.metadata is held
    assert qc.num_clbits == 2
    assert [item.name for item in qc.data] == ['x', 'barrier', 'measure', 'measure']
    assert type(qc.data[1].operation) is Barrier
    assert qc.data[1].qubits == tuple(qc.qubits)
    assert qc.data[2].clbits == (qc.clbits[0],)
    assert qc.data[3].clbits == (qc.clbits[1],)
"""
    namespace = {}
    exec(code, namespace)
    exec(test, namespace)
    namespace["check"](namespace["answer"])
    task = JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="barrier-fixture",
            family_id="barrier-fixture",
            prompt="Implement answer.",
            entry_point="answer",
            prompt_format="standalone_function",
        ),
        canonical_solution="private reference",
        upstream_test=test,
        upstream_difficulty="fixture",
    )
    result = UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
    ).evaluate(task, code)
    assert result.outcome == "pass", result

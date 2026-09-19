import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Gate, Instruction
from qiskit.circuit.library import RXGate, XGate

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="ops", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, seq=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=seq), sequence=seq))["value"]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Gate("g", 1, [0.2]),
        lambda: Instruction("i", 1, 1, [0.2]),
        lambda: RXGate(0.2),
        lambda: XGate().to_mutable(),
    ],
)
def test_operation_actual_dictionary_and_parameter_list(factory):
    a, b = arenas()
    op = factory()
    remote, attrs, params = transfer(a, b, (op, vars(op), op.params))
    assert type(remote) is type(op) and vars(remote) is attrs and remote.params is params
    remote.params.append(0.7)
    assert transfer(b, a, remote) is op and op.params[-1] == 0.7


def test_definition_shared_with_root_and_not_synthesized():
    a, b = arenas()
    op = RXGate(0.2)
    assert op._definition is None
    remote = transfer(a, b, op)
    assert remote._definition is None and op._definition is None
    definition = QuantumCircuit(1)
    definition.x(0)
    op._definition = definition
    remote, held = transfer(a, b, (op, definition), 2)
    assert remote._definition is held
    held.h(0)
    assert transfer(b, a, remote, 1) is op
    assert op._definition is definition and len(definition.data) == 2


def test_shared_retained_operation_keeps_native_cached_parameters():
    a, b = arenas()
    gate = Gate("original", 1, [0.2])
    first, second = QuantumCircuit(1), QuantumCircuit(1)
    first.append(gate, [0], copy=False)
    gate.params = [0.4]
    second.append(gate, [0], copy=False)
    gate.params = [0.8]
    gate.name = "changed"
    x, y, remote, params = transfer(a, b, (first, second, gate, gate.params))
    assert x.data[0].operation is y.data[0].operation is remote
    assert remote.params is params and params == [0.8]
    assert x.data[0].params == [0.2] and y.data[0].params == [0.4]
    assert x.data[0].name == y.data[0].name == "original" and remote.name == "changed"
    remote.params.append(0.9)
    assert transfer(b, a, remote) is gate
    assert gate.params == [0.8, 0.9] and first.data[0].params == [0.2]


def test_retained_rx_gate_not_flattened():
    a, b = arenas()
    gate = RXGate(0.2)
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0], copy=False)
    remote, held = transfer(a, b, (circuit, gate))
    assert remote.data[0].operation is held
    held.params[0] = 0.9
    transfer(b, a, remote)
    assert circuit.data[0].operation is gate and gate.params == [0.9]
    assert circuit.data[0].params == [0.2]


def test_equal_parameter_replacement_preserves_detached_alias():
    a, b = arenas()
    gate = Gate("g", 1, [0.2])
    original = gate.params
    remote, old = transfer(a, b, (gate, original))
    remote.params = [0.2]
    old.append(0.5)
    transfer(b, a, remote)
    assert gate.params == [0.2] and gate.params is not original and original == [0.2, 0.5]


def test_instruction_class_selector_cannot_change_live_class():
    a, b = arenas()
    gate = Gate("g", 1, [])
    remote = transfer(a, b, gate)
    wire = a.snapshot({"value": gate}, sequence=2)
    record = next(r for r in wire["nodes"] if r["kind"] == "python_instruction")
    record["state"]["class"] = "instruction"
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert type(remote) is Gate


def test_retained_parameter_array_keeps_actual_storage():
    import numpy as np

    a, b = arenas()
    matrix = np.eye(2)
    gate = Instruction("array", 1, 0, [matrix])
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0], copy=False)
    remote, held = transfer(a, b, (circuit, matrix))
    assert remote.data[0].operation.params[0] is held
    assert remote.data[0].params[0] is held
    held[0, 0] = 0.5
    transfer(b, a, remote)
    assert matrix[0, 0] == 0.5


def test_retained_symbolic_parameters_preserve_vector_relationship():
    from qiskit.circuit import ParameterVector

    a, b = arenas()
    vector = ParameterVector("v", 1)
    gate = RXGate(vector[0])
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0], copy=False)
    remote, held = transfer(a, b, (circuit, vector))
    assert remote.data[0].operation.params[0].vector is held
    assert remote.data[0].params[0].vector is held
    assert transfer(b, a, remote) is circuit


def test_retained_instruction_classical_operands():
    a, b = arenas()
    op = Instruction("custom", 1, 1, [])
    circuit = QuantumCircuit(1, 2)
    circuit.append(op, [0], [1], copy=False)
    remote, held = transfer(a, b, (circuit, op))
    assert remote.data[0].operation is held
    assert remote.data[0].clbits == (remote.clbits[1],)


def test_late_missing_cached_parameter_reference_leaves_live_objects_unchanged():
    a, b = arenas()
    gate = Gate("g", 1, [0.2])
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0], copy=False)
    remote, held = transfer(a, b, (circuit, gate))
    gate.params[0] = 0.7
    wire = a.snapshot({"value": circuit}, sequence=2)
    record = next(r for r in wire["nodes"] if r["kind"] == "circuit_data")
    record["state"]["operations"][0]["params"] = [{"value": {"ref": "j:999999"}}]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert held.params == [0.2] and remote.data[0].params == [0.2]


def test_recursive_definition_and_label_cache_survive():
    a, b = arenas()
    gate = Gate("g", 1, [], label="before")
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0], copy=False)
    gate._definition = circuit
    gate.label = "after"
    remote, held = transfer(a, b, (circuit, gate))
    assert held._definition is remote and remote.data[0].operation is held
    assert remote.data[0].label == "before" and held.label == "after"
    assert transfer(b, a, remote) is circuit
    assert gate._definition is circuit


@pytest.mark.parametrize("mutation", ["class", "params", "operand"])
def test_malformed_retained_state_is_rejected_before_live_update(mutation):
    a, b = arenas()
    gate = Gate("g", 1, [0.2])
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0], copy=False)
    remote, held = transfer(a, b, (circuit, gate))
    gate.params[0] = 0.7
    wire = a.snapshot({"value": circuit}, sequence=2)
    operation = next(r for r in wire["nodes"] if r["kind"] == "circuit_data")["state"][
        "operations"
    ][0]
    if mutation == "class":
        next(r for r in wire["nodes"] if r["kind"] == "python_instruction")["state"]["class"] = (
            "arbitrary.module.Constructor"
        )
    elif mutation == "params":
        operation["params"] = [{"arbitrary": 1}]
    else:
        operation["qubits"] = [500]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert held.params == [0.2] and remote.data[0].operation is held


def test_custom_instruction_subclass_is_not_reconstructed_as_base():
    class Custom(Gate):
        pass

    a, _ = arenas()
    with pytest.raises(WireError, match="Unsupported graph object"):
        a.snapshot({"value": Custom("g", 1, [])}, sequence=1)


@pytest.mark.parametrize("before,after", [(1, 2), (2, 3), (3, 1)])
def test_stale_native_arity_is_preserved(before, after):
    from qiskit.dagcircuit import DAGOpNode

    a, b = arenas()
    gate = Instruction("g", before, 1, [])
    circuit = QuantumCircuit(3, 2)
    circuit.append(gate, list(range(before)), [0], copy=False)
    gate._num_qubits = after
    gate._num_clbits = 2
    remote, held = transfer(a, b, (circuit, gate))
    native = DAGOpNode.from_instruction(remote.data[0])
    assert native.num_qubits == before and native.num_clbits == 1
    assert held.num_qubits == after and held.num_clbits == 2
    assert transfer(b, a, remote) is circuit
    native = DAGOpNode.from_instruction(circuit.data[0])
    assert native.num_qubits == before and native.num_clbits == 1

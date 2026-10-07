import copy

import pytest
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import Operator

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="qc", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, seq=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=seq), sequence=seq))["value"]


def test_circuit_update_retains_root_metadata_and_held_data_wrapper():
    a, b = arenas()
    circuit = QuantumCircuit(2, metadata={"seen": []})
    metadata, wrapper = circuit.metadata, circuit.data
    remote, held, view = transfer(a, b, (circuit, metadata, wrapper))
    assert remote.metadata is held and view._circuit is remote
    remote.x(1)
    remote.metadata["seen"].append("changed")
    result = transfer(b, a, remote)
    assert result is circuit and circuit.metadata is metadata and wrapper._circuit is circuit
    assert metadata == {"seen": ["changed"]} and wrapper[0].operation.name == "x"


def test_circuit_components_and_instance_dictionary_aliases():
    a, b = arenas()
    circuit = QuantumCircuit(2)
    result, attrs, builder, data, cache = transfer(
        a, b, (circuit, vars(circuit), circuit._builder_api, circuit._data, circuit.qubits)
    )
    assert vars(result) is attrs and result._builder_api is builder and builder.circuit is result
    assert result._data is data and result.qubits is cache


def test_two_shallow_copied_circuits_keep_shared_native_data_and_builder():
    a, b = arenas()
    first = QuantumCircuit(2)
    second = copy.copy(first)
    assert second._data is first._data and second._builder_api.circuit is first
    x, y = transfer(a, b, (first, second))
    assert x is not y and x._data is y._data
    assert y._builder_api is x._builder_api and y._builder_api.circuit is x


def test_register_addition_keeps_root_and_detached_cache():
    a, b = arenas()
    circuit = QuantumCircuit(2)
    old = circuit.qubits
    remote, held = transfer(a, b, (circuit, old))
    remote.add_register(QuantumRegister(1, "extra"))
    transfer(b, a, remote)
    assert circuit.num_qubits == 3 and circuit.qubits is not old and len(old) == len(held) == 2


def test_packed_gates_keep_order_parameters_labels_and_unitary():
    a, b = arenas()
    circuit = QuantumCircuit(2, global_phase=0.3)
    circuit.h(0)
    circuit.rx(0.7, 1)
    circuit.cx(0, 1)
    circuit.rz(-0.2, 0)
    remote = transfer(a, b, circuit)
    assert remote.count_ops() == circuit.count_ops()
    assert Operator(remote) == Operator(circuit)
    assert remote.data[1].operation is not remote.data[1].operation
    remote.data.pop(0)
    transfer(b, a, remote)
    assert circuit.count_ops() == {"rx": 1, "cx": 1, "rz": 1}


def test_packed_symbolic_vector_parameters_keep_vector_owner():
    a, b = arenas()
    vector = ParameterVector("theta", 2)
    circuit = QuantumCircuit(1)
    circuit.rx(vector[0], 0)
    circuit.rz(vector[1] + 1, 0)
    remote, v = transfer(a, b, (circuit, vector))
    assert all(p.vector is v for p in remote.parameters)
    expected = circuit.assign_parameters({vector[0]: 0.2, vector[1]: 0.3})
    actual = remote.assign_parameters({v[0]: 0.2, v[1]: 0.3})
    assert Operator(expected) == Operator(actual)
    assert transfer(b, a, remote) is circuit


def test_metadata_equal_replacement_retains_old_shared_dictionary():
    a, b = arenas()
    circuit = QuantumCircuit(1, metadata={"x": []})
    original = circuit.metadata
    remote, held = transfer(a, b, (circuit, original))
    remote.metadata = {"x": []}
    held["x"].append(7)
    transfer(b, a, remote)
    assert circuit.metadata is not original and circuit.metadata == {"x": []}
    assert original == {"x": [7]}


def test_late_invalid_circuit_update_keeps_live_metadata_and_instructions():
    a, b = arenas()
    circuit = QuantumCircuit(1)
    remote = transfer(a, b, circuit)
    metadata = remote.metadata
    circuit.x(0)
    circuit.metadata["changed"] = True
    wire = a.snapshot({"value": (circuit, [1])}, sequence=2)
    next(n for n in wire["nodes"] if n["kind"] == "list" and n["state"] == [1])["state"] = [
        {"ref": "j:999"}
    ]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert remote.metadata is metadata and metadata == {} and len(remote.data) == 0


@pytest.mark.parametrize("mutation", ["name", "qubits", "params", "label", "expression"])
def test_malformed_packed_gate_fails_before_live_mutation(mutation):
    a, b = arenas()
    circuit = QuantumCircuit(2)
    remote = transfer(a, b, circuit)
    held = remote.qubits
    circuit.rx(0.5, 0)
    wire = a.snapshot({"value": circuit}, sequence=2)
    op = next(n for n in wire["nodes"] if n["kind"] == "circuit_data")["state"]["operations"][0]
    if mutation == "name":
        op["name"] = "__import__"
    elif mutation == "qubits":
        op["qubits"] = [2]
    elif mutation == "params":
        op["params"] = []
    elif mutation == "label":
        op["label"] = {}
    else:
        op["params"] = [
            {"kind": "expression", "program": [{"op": "exec", "lhs": None, "rhs": None}]}
        ]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert remote.qubits is held and len(remote.data) == 0


def test_retained_python_gate_is_not_flattened_into_packed_value():
    from qiskit.circuit.library import RXGate

    a, _ = arenas()
    circuit = QuantumCircuit(1)
    gate = RXGate(0.2)
    circuit.append(gate, [0], copy=False)
    assert circuit.data[0].operation is gate
    b = arenas()[1]
    remote, held = transfer(a, b, (circuit, gate))
    assert remote.data[0].operation is held


def test_adding_quantum_register_preserves_classical_registers_and_phase():
    a, b = arenas()
    circuit = QuantumCircuit(2, 1, global_phase=0.7)
    circuit.h(0)
    remote = transfer(a, b, circuit)
    classical = remote.cregs
    remote.add_register(QuantumRegister(1, "extra"))
    transfer(b, a, remote)
    assert circuit.num_qubits == 3 and circuit.num_clbits == 1 and circuit.cregs == classical
    assert circuit.global_phase == 0.7 and circuit.count_ops() == {"h": 1}


def test_held_wrapper_follows_replaced_native_data_without_replacing_circuit():
    a, b = arenas()
    circuit = QuantumCircuit(1)
    wrapper = circuit.data
    remote, view, original = transfer(a, b, (circuit, wrapper, circuit._data))
    replacement = QuantumCircuit(1)
    replacement.z(0)
    remote._data = replacement._data
    transfer(b, a, remote)
    assert wrapper._circuit is circuit and wrapper[0].operation.name == "z"
    assert view._circuit is remote and len(original) == 0


def test_invalid_native_packed_parameter_is_wire_error_before_live_update():
    a, b = arenas()
    circuit = QuantumCircuit(1)
    remote = transfer(a, b, circuit)
    circuit.rx(0.2, 0)
    wire = a.snapshot({"value": circuit}, sequence=2)
    op = next(n for n in wire["nodes"] if n["kind"] == "circuit_data")["state"]["operations"][0]
    op["params"] = [{"kind": "literal", "value": {"kind": "complex_v1", "real": 1.0, "imag": 1.0}}]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert len(remote.data) == 0


def test_packed_standard_label_preserved():
    from qiskit.circuit import CircuitInstruction
    from qiskit.circuit.library import RXGate

    a, b = arenas()
    circuit = QuantumCircuit(1)
    circuit._data.append(
        CircuitInstruction.from_standard(
            RXGate._standard_gate, circuit.qubits, [0.3], label="rotation α"
        )
    )
    remote = transfer(a, b, circuit)
    assert remote.data[0].label == "rotation α"
    assert transfer(b, a, remote) is circuit

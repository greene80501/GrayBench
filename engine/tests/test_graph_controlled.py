import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import ControlledGate
from qiskit.circuit.library import CRXGate, RXGate
from qiskit.quantum_info import Operator

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="controlled", limits=GraphLimits())
        for s in ("judge", "candidate")
    )


def transfer(a, b, value, seq=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=seq), sequence=seq))["value"]


@pytest.mark.parametrize("control", [0, 1])
def test_controlled_actual_components_and_unsynthesized_definition(control):
    a, b = arenas()
    gate = CRXGate(0.2, ctrl_state=control)
    remote, attrs, base, params, raw = transfer(
        a, b, (gate, vars(gate), gate.base_gate, gate.params, gate._params)
    )
    assert type(remote) is CRXGate and vars(remote) is attrs
    assert remote.base_gate is base and remote.params is params is base.params
    assert remote._params is raw and raw is not params
    assert remote._definition is None and base._definition is None
    params[0] = 0.9
    assert transfer(b, a, remote) is gate and gate.params == [0.9]


@pytest.mark.parametrize("initial,final", [(0, 1), (1, 0)])
def test_control_change_preserves_native_representation_and_parameter_cache(initial, final):
    a, b = arenas()
    gate = CRXGate(0.2, ctrl_state=initial)
    circuit = QuantumCircuit(2)
    circuit.append(gate, [0, 1], copy=False)
    original_name = circuit.data[0].name
    original_standard = circuit.data[0].is_standard_gate()
    gate.ctrl_state = final
    gate.params[0] = 0.9
    remote, held, base = transfer(a, b, (circuit, gate, gate.base_gate))
    np.testing.assert_allclose(Operator(remote).data, Operator(circuit).data)
    item = remote.data[0]
    assert item.operation is held and held.base_gate is base
    assert item.name == original_name and item.is_standard_gate() is original_standard
    assert item.params == [0.2] and held.params == [0.9] and held.ctrl_state == final
    assert transfer(b, a, remote) is circuit
    assert circuit.data[0].operation is gate and gate.params == [0.9]
    assert (
        circuit.data[0].name == original_name
        and circuit.data[0].is_standard_gate() is original_standard
    )


def test_two_controlled_gates_share_base_and_raw_definition():
    a, b = arenas()
    base = RXGate(0.2)
    left = ControlledGate("left", 2, [0.2], num_ctrl_qubits=1, base_gate=base)
    right = ControlledGate("right", 2, [0.2], num_ctrl_qubits=1, base_gate=base)
    left.base_gate = right.base_gate = base
    definition = QuantumCircuit(2)
    definition.x(0)
    left._definition = right._definition = definition
    x, y, held, body = transfer(a, b, (left, right, base, definition))
    assert x.base_gate is y.base_gate is held and x._definition is y._definition is body
    held.params[0] = 0.7
    body.h(1)
    transfer(b, a, (x, y))
    assert left.params is right.params is base.params and base.params == [0.7]
    assert left._definition is definition and len(definition.data) == 2


def test_controlled_base_cycle_is_rejected_without_recursing_properties():
    a, _ = arenas()
    gate = CRXGate(0.2)
    gate.base_gate = gate
    with pytest.raises(WireError):
        a.snapshot({"value": gate}, sequence=1)


def test_malformed_control_flag_leaves_existing_base_unchanged():
    a, b = arenas()
    gate = CRXGate(0.2)
    remote = transfer(a, b, gate)
    gate.params[0] = 0.9
    wire = a.snapshot({"value": gate}, sequence=2)
    record = next(
        r for r in wire["nodes"] if r["kind"] == "python_instruction" and "_open_ctrl" in r["state"]
    )
    record["state"]["_open_ctrl"] = "yes"
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert remote.params == [0.2]


@pytest.mark.parametrize("initial,final", [(0, 1), (1, 0)])
def test_control_update_on_existing_remote_keeps_old_native_cache(initial, final):
    a, b = arenas()
    gate = CRXGate(0.2, ctrl_state=initial)
    circuit = QuantumCircuit(2)
    circuit.append(gate, [0, 1], copy=False)
    remote, held, params = transfer(a, b, (circuit, gate, gate.params))
    held.ctrl_state = final
    params[0] = 0.8
    transfer(b, a, remote)
    assert circuit.data[0].operation is gate and gate.ctrl_state == final
    assert gate.params == [0.8] and circuit.data[0].params == [0.2]
    assert circuit.data[0].is_standard_gate() is bool(initial)


def test_generic_open_control_name_and_cached_params():
    a, b = arenas()
    gate = ControlledGate(
        "custom_o3", 2, [0.2], num_ctrl_qubits=1, base_gate=RXGate(0.2), ctrl_state=0
    )
    circuit = QuantumCircuit(2)
    circuit.append(gate, [0, 1], copy=False)
    name = circuit.data[0].name
    gate.name = "renamed"
    gate.params[0] = 0.9
    remote, held = transfer(a, b, (circuit, gate))
    assert remote.data[0].operation is held and remote.data[0].name == name
    assert remote.data[0].params == [0.2] and held.params == [0.9]
    assert not remote.data[0].is_standard_gate()


def test_base_replacement_keeps_detached_old_base():
    a, b = arenas()
    gate = CRXGate(0.2)
    old = gate.base_gate
    remote, held = transfer(a, b, (gate, old))
    remote.base_gate = RXGate(0.2)
    held.params[0] = 0.6
    transfer(b, a, remote)
    assert gate.base_gate is not old and gate.params == [0.2] and old.params == [0.6]


def test_forged_native_representation_selector_cannot_mutate_existing_base():
    a, b = arenas()
    gate = CRXGate(0.2)
    circuit = QuantumCircuit(2)
    circuit.append(gate, [0, 1], copy=False)
    remote, held = transfer(a, b, (circuit, gate))
    gate.params[0] = 0.9
    wire = a.snapshot({"value": circuit}, sequence=2)
    record = next(r for r in wire["nodes"] if r["kind"] == "circuit_data")
    record["state"]["operations"][0]["native_standard"] = "true"
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert held.params == [0.2] and remote.data[0].operation is held


def test_nested_controlled_base_params_delegate_to_same_leaf():
    a, b = arenas()
    base = CRXGate(0.2, ctrl_state=0)
    gate = ControlledGate("outer", 3, [0.2], num_ctrl_qubits=1, base_gate=base, ctrl_state=0)
    gate.base_gate = base
    circuit = QuantumCircuit(3)
    circuit.append(gate, [0, 1, 2], copy=False)
    base.params[0] = 0.7
    remote, held, inner = transfer(a, b, (circuit, gate, base))
    assert held.base_gate is inner and held.params is inner.base_gate.params
    assert remote.data[0].params == [0.2] and held.params == [0.7]
    assert transfer(b, a, remote) is circuit

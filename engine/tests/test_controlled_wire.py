import copy

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import ControlledGate, Parameter
from qiskit.circuit.library import HGate, MCXGate, RYGate
from qiskit.quantum_info import Operator

from graybench.circuit_wire import WireError
from graybench.value_wire import decode, encode


@pytest.mark.parametrize("ctrl_state", [0, 1, 2, 3])
def test_generic_controlled_gate_retains_open_state_and_raw_cache(ctrl_state):
    original = HGate().control(2, ctrl_state=ctrl_state, label="control-label", annotated=False)
    original.name = "custom_control"
    original._definition.metadata = {"source": "cached"}
    before = copy.deepcopy(original._definition)
    restored = decode(encode(original))
    assert type(restored) is ControlledGate
    assert restored.name == original.name
    assert restored._name == original._name
    assert restored.ctrl_state == ctrl_state
    assert restored.label == original.label
    assert restored._definition == before == original._definition
    assert restored._definition.metadata == before.metadata
    np.testing.assert_allclose(Operator(restored).data, Operator(original).data)


@pytest.mark.parametrize("ctrl_state", [0, 5, 15])
def test_mcx_retains_class_state_lazy_cache_and_permuted_operands(ctrl_state):
    gate = MCXGate(4, ctrl_state=ctrl_state, label="multi")
    circuit = QuantumCircuit(6)
    circuit.append(gate, [5, 1, 3, 0, 2])
    restored = decode(encode(circuit))
    result = restored.data[0].operation
    assert type(result) is MCXGate
    assert result.ctrl_state == ctrl_state
    assert result._definition is None and gate._definition is None
    assert [restored.find_bit(q).index for q in restored.data[0].qubits] == [5, 1, 3, 0, 2]
    np.testing.assert_allclose(Operator(restored).data, Operator(circuit).data)


def test_controlled_symbolic_base_and_custom_cache_survive_without_repair():
    theta = Parameter("theta")
    definition = QuantumCircuit(3, name="custom")
    definition.ry(theta, 2)
    definition.metadata = {"intentionally": "not a controlled rotation"}
    gate = ControlledGate(
        "custom",
        3,
        [theta],
        num_ctrl_qubits=2,
        base_gate=RYGate(theta),
        definition=definition,
        ctrl_state=1,
    )
    restored = decode(encode(gate))
    assert type(restored.base_gate) is type(gate.base_gate)
    assert restored.params == gate.params == [theta]
    assert restored._definition == definition
    assert restored._definition.metadata == definition.metadata
    for item in (gate, restored):
        circuit = QuantumCircuit(3)
        circuit.append(item, range(3))
        bound = circuit.assign_parameters({theta: 0.32})
        if item is gate:
            expected = Operator(bound).data
        else:
            np.testing.assert_allclose(Operator(bound).data, expected)


def test_controlled_codec_rejects_malformed_state_and_wire():
    gate = HGate().control(2, annotated=False)
    wire = encode(gate)
    for field, value in (
        ("controls", 3),
        ("state", 4),
        ("state", True),
        ("class", "Custom"),
        ("qubits", 600),
        ("extra", 1),
    ):
        bad = copy.deepcopy(wire)
        bad[field] = value
        with pytest.raises(WireError):
            decode(bad)
    gate._open_ctrl = True
    with pytest.raises(WireError):
        encode(gate)
    gate._open_ctrl = False
    gate.extra = True
    with pytest.raises(WireError):
        encode(gate)


def test_controlled_recursive_cache_is_bounded():
    gate = HGate().control(2, annotated=False)
    circuit = QuantumCircuit(3)
    circuit.append(gate, range(3), copy=False)
    gate._definition = circuit
    with pytest.raises(WireError, match="nesting"):
        encode(gate)


def test_controlled_custom_base_and_both_definitions_retain_metadata():
    base = QuantumCircuit(2, name="custom-base")
    base.x(0)
    base.h(1)
    gate = base.to_gate().control(2, annotated=False)
    gate.base_gate.label = "base-label"
    gate.base_gate.definition.metadata = {"base": [1, 2]}
    gate._definition.metadata = {"controlled": True}
    circuit = QuantumCircuit(4)
    circuit.append(gate, [0, 3, 1, 2])
    restored = decode(encode(circuit))
    result = restored.data[0].operation
    assert result.base_gate.label == "base-label"
    assert result.base_gate.definition.metadata == {"base": [1, 2]}
    assert result._definition.metadata == {"controlled": True}
    np.testing.assert_allclose(Operator(restored).data, Operator(circuit).data)


def test_controlled_base_missing_or_inconsistent_dimensions_is_unsupported():
    gate = HGate().control(2, annotated=False)
    gate.base_gate = None
    with pytest.raises(WireError):
        encode(gate)
    gate.base_gate = HGate()
    gate._num_qubits = 4
    with pytest.raises(WireError):
        encode(gate)


def test_controlled_matrix_budget_includes_base_and_cached_definition():
    from qiskit.circuit.library import UnitaryGate

    matrix = np.eye(128, dtype=complex)
    definition = QuantumCircuit(8)
    definition.append(UnitaryGate(matrix), range(7))
    definition.append(UnitaryGate(matrix), range(7))
    gate = ControlledGate(
        "matrix-budget",
        8,
        [matrix],
        num_ctrl_qubits=1,
        base_gate=UnitaryGate(matrix),
        definition=definition,
    )
    with pytest.raises(WireError, match="Total matrix storage"):
        decode(encode(gate))

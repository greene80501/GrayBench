import copy

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit.circuit.library import DiagonalGate, HamiltonianGate
from qiskit.quantum_info import Operator

from graybench.circuit_wire import WireError
from graybench.value_wire import decode, encode


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("kind", ["hamiltonian", "diagonal"])
def test_numeric_gate_preserves_type_parameters_and_custom_definition(kind, nested):
    gate = (
        HamiltonianGate(np.array([[0, 1j], [-1j, 0]]), 0.7)
        if kind == "hamiltonian"
        else DiagonalGate([1, 1j])
    )
    gate.name = "user_name"
    gate.label = "user_label"
    custom = QuantumCircuit(1, name="cached")
    custom.x(0)
    custom.metadata = {"custom": True}
    gate.definition = custom
    original = gate
    if nested:
        original = QuantumCircuit(1)
        original.append(gate, [0])
    restored = decode(encode(original))
    result = restored.data[0].operation if nested else restored
    assert type(result) is type(gate)
    assert result.name == gate.name and result.label == gate.label
    assert result.definition == custom
    assert result.definition.name == custom.name
    assert result.definition.metadata == custom.metadata
    for a, b in zip(result.params, gate.params, strict=True):
        np.testing.assert_array_equal(a, b)
    np.testing.assert_allclose(Operator(restored).data, Operator(original).data)


def test_hamiltonian_symbolic_time_and_matrix_bytes_survive():
    time = Parameter("time")
    gate = HamiltonianGate(np.eye(2), time / 3)
    gate.params[0] = gate.params[0].astype(">c16")
    restored = decode(encode(gate))
    assert restored.params[1] == time / 3
    assert restored.params[0].dtype == gate.params[0].dtype
    assert restored.params[0].tobytes() == gate.params[0].tobytes()
    assert gate._definition is None and restored._definition is None


@pytest.mark.parametrize("kind", ["hamiltonian", "diagonal"])
def test_numeric_gate_does_not_repair_invalid_parameters(kind):
    gate = HamiltonianGate(np.eye(2), 1.0) if kind == "hamiltonian" else DiagonalGate([1, 1])
    if kind == "hamiltonian":
        gate.params[0][0, 1] = 2j
    else:
        gate.params[0] = 3 + 4j
    restored = decode(encode(gate))
    for a, b in zip(restored.params, gate.params, strict=True):
        np.testing.assert_array_equal(a, b)


def test_numeric_gate_rejects_extra_state_and_bad_wire():
    gate = DiagonalGate([1, 1j])
    wire = encode(gate)
    gate.custom = True
    with pytest.raises(WireError):
        encode(gate)
    for key, value in [("qubits", 30), ("class", "custom"), ("params", []), ("extra", True)]:
        bad = copy.deepcopy(wire)
        bad[key] = value
        with pytest.raises(WireError):
            decode(bad)


def test_cached_hamiltonian_definition_and_uncached_diagonal_behavior():
    gate = HamiltonianGate(np.array([[1, 0], [0, -1]]), -0.37)
    _ = gate.definition
    restored = decode(encode(gate))
    np.testing.assert_allclose(Operator(restored).data, Operator(gate).data)
    assert restored.definition == gate.definition
    diagonal = DiagonalGate([1, 1j, -1, -1j])
    restored_diagonal = decode(encode(diagonal))
    assert diagonal._definition is None and restored_diagonal._definition is None
    np.testing.assert_allclose(Operator(restored_diagonal).data, Operator(diagonal).data)
    # UCRZ inside Qiskit's synthesized cached definition has no codec yet.
    _ = diagonal.definition
    with pytest.raises(WireError, match="Unsupported instruction"):
        encode(diagonal)


def test_numeric_gate_subclasses_dimensions_and_recursive_cache_rejected():
    class CustomDiagonal(DiagonalGate):
        pass

    with pytest.raises(WireError):
        encode(CustomDiagonal([1, 1]))
    gate = HamiltonianGate(np.eye(2), 1)
    gate.params[0] = np.eye(3, dtype=complex)
    with pytest.raises(WireError, match="shape"):
        encode(gate)
    gate = DiagonalGate([1, 1])
    definition = QuantumCircuit(1)
    definition.append(gate, [0], copy=False)
    gate.definition = definition
    with pytest.raises(WireError, match="nesting"):
        encode(gate)


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_numeric_gate_matrix_budget_is_shared_with_nested_unitaries(nested, mixed):
    from qiskit.circuit.library import UnitaryGate

    circuit = QuantumCircuit(7)
    for index in range(3):
        matrix = np.eye(128, dtype=complex)
        gate = UnitaryGate(matrix) if mixed and index == 0 else HamiltonianGate(matrix, 1)
        if nested:
            inner = QuantumCircuit(7)
            inner.append(gate, range(7))
            gate = inner.to_gate()
        circuit.append(gate, range(7))
    with pytest.raises(WireError, match="Total matrix storage"):
        decode(encode(circuit))

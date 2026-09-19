import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import LinearFunction

from graybench.circuit_wire import WireError
from graybench.value_wire import decode, encode


def test_linear_function_preserves_original_and_cached_definition():
    original = QuantumCircuit(3, name="original")
    original.cx(0, 1)
    original.swap(1, 2)
    original.metadata = {"source": "public circuit"}
    op = LinearFunction(original)
    # Public fields can diverge; do not silently recompute one from another.
    op.linear[0, 0] = not op.linear[0, 0]
    op.name = "renamed"
    op.label = "labeled"
    cached = QuantumCircuit(3, name="custom cached definition")
    cached.x(0)
    cached.metadata = {"deliberately": "different"}
    op.definition = cached
    restored = decode(encode(op))
    assert type(restored) is LinearFunction
    np.testing.assert_array_equal(restored.linear, op.linear)
    assert restored.original_circuit == original
    assert restored.original_circuit.metadata == original.metadata
    assert restored.definition == cached
    assert restored.definition.metadata == cached.metadata
    assert (restored.name, restored.label) == (op.name, op.label)


def test_linear_function_embedded_and_unvalidated_matrix_remain_exact():
    # The codec must not repair singular candidate matrices or synthesize definitions.
    matrix = np.zeros((3, 3), dtype=bool)
    op = LinearFunction(matrix)
    circuit = QuantumCircuit(3)
    circuit.append(op, [2, 0, 1])
    restored = decode(encode(circuit))
    result = restored.data[0].operation
    assert type(result) is LinearFunction
    np.testing.assert_array_equal(result.linear, matrix)
    assert result.original_circuit is None
    assert result._definition is None
    assert [restored.find_bit(q).index for q in restored.data[0].qubits] == [2, 0, 1]


def test_malformed_linear_matrix_rejected():
    value = encode(LinearFunction(np.eye(2, dtype=bool)))
    value["linear"]["shape"] = [1, 4]
    with pytest.raises(WireError):
        decode(value)


def test_linear_function_metadata_cannot_select_a_constructor():
    value = encode(LinearFunction(np.eye(2, dtype=bool)))
    value["constructor"] = "arbitrary-code"
    with pytest.raises(WireError):
        decode(value)


def test_linear_function_cycle_remains_bounded():
    from graybench.circuit_wire import WireLimitError

    op = LinearFunction(np.eye(2, dtype=bool))
    circuit = QuantumCircuit(2)
    circuit.append(op, [0, 1], copy=False)
    op.params[1] = circuit
    with pytest.raises(WireLimitError, match="nesting"):
        encode(op)

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import CNOTDihedral

from graybench.circuit_wire import WireError
from graybench.value_wire import decode, encode


def example():
    circuit = QuantumCircuit(3)
    circuit.cx(0, 1)
    circuit.t(1)
    circuit.x(2)
    circuit.ccz(0, 1, 2)
    return CNOTDihedral(circuit)


def test_dihedral_preserves_representation_and_composition():
    original = example()
    restored = decode(encode(original))
    assert type(restored) is CNOTDihedral
    assert restored == original
    for name in ("linear", "shift"):
        np.testing.assert_array_equal(getattr(original, name), getattr(restored, name))
        assert getattr(original, name).dtype == getattr(restored, name).dtype
    for name in ("weight_1", "weight_2", "weight_3"):
        np.testing.assert_array_equal(getattr(original.poly, name), getattr(restored.poly, name))
    np.testing.assert_allclose(restored.to_matrix(), original.to_matrix())
    composed = original.compose(original)
    restored_composed = decode(encode(composed))
    assert type(restored_composed.shift) is type(composed.shift)
    assert [type(x) for x in restored_composed.shift] == [type(x) for x in composed.shift]
    np.testing.assert_array_equal(restored_composed.shift, composed.shift)
    np.testing.assert_allclose(restored_composed.to_matrix(), composed.to_matrix())


def test_invalid_dihedral_coefficients_are_preserved_not_repaired():
    original = example()
    original.linear[0] = 0
    original.poly.weight_0 = 11
    original.poly.weight_1[0] = -3
    restored = decode(encode(original))
    assert restored.poly.weight_0 == 11
    assert type(restored.poly.weight_0) is int
    assert restored.poly.weight_1[0] == -3
    np.testing.assert_array_equal(restored.linear, original.linear)


def test_dihedral_unmodeled_state_is_not_silently_discarded():
    original = example()
    original.extra = "custom"
    with pytest.raises(WireError):
        encode(original)
    original = example()
    original.poly.extra = "custom"
    with pytest.raises(WireError):
        encode(original)
    with pytest.raises(WireError):
        encode(example()([0, 1, 2]))


def test_dihedral_inconsistent_internal_qubit_count_is_rejected():
    original = example()
    original._num_qubits = 4
    with pytest.raises(WireError):
        encode(original)


def test_dihedral_shape_and_dimension_payloads_are_validated():
    value = encode(example())
    value["qubits"] = 1000000
    with pytest.raises(WireError):
        decode(value)


def test_dihedral_list_shift_and_polynomial_metadata_are_checked():
    original = example().compose(example())
    value = encode(original)
    value["shift"]["items"] = []
    with pytest.raises(WireError):
        decode(value)
    original.poly.nc2 = 0
    with pytest.raises(WireError):
        encode(original)


def test_dihedral_numpy_constant_and_nondefault_array_dtype_remain_exact():
    original = example()
    original.poly.weight_0 = np.int16(3)
    original.linear = original.linear.astype(">i4")
    restored = decode(encode(original))
    assert type(restored.poly.weight_0) is np.int16
    assert restored.linear.dtype.str == ">i4"
    assert restored.linear.tobytes() == original.linear.tobytes()
    value = encode(example())
    value["linear"] = encode(np.zeros((2, 2), dtype=np.int8))
    with pytest.raises(WireError):
        decode(value)
    value = encode(example())
    value["constructor"] = "os.system"
    with pytest.raises(WireError):
        decode(value)

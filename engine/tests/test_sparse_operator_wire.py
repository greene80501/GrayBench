import numpy as np
import pytest
from qiskit.circuit import Parameter
from qiskit.quantum_info import ScalarOp, SparsePauliOp

from graybench.value_wire import decode, encode


def test_scalar_preserves_coefficient_subsystems_and_bound_qargs():
    original = ScalarOp((2, 3), coeff=np.complex64(-2 + 3j)).reshape(
        input_dims=(6,), output_dims=(3, 2)
    )(5)
    restored = decode(encode(original))
    assert type(restored) is ScalarOp
    assert type(restored.coeff) is np.complex64
    assert restored.coeff == -2 + 3j
    assert restored.input_dims() == (6,)
    assert restored.output_dims() == (3, 2)
    assert restored.qargs == (5,)
    np.testing.assert_array_equal(restored.to_matrix(), original.to_matrix())


def test_sparse_preserves_order_duplicates_zeros_and_pauli_phases():
    original = SparsePauliOp(["YI", "XZ", "XZ", "II"], [1, 2j, -2j, 0])
    original.paulis.phase = [1, 2, 3, 0]
    original = original.reshape(input_dims=(4,), output_dims=(2, 2))(7)
    restored = decode(encode(original))
    assert type(restored) is SparsePauliOp
    assert restored.size == 4
    np.testing.assert_array_equal(restored.paulis.phase, [1, 2, 3, 0])
    np.testing.assert_array_equal(restored.coeffs, [1, 2j, -2j, 0])
    np.testing.assert_array_equal(restored.paulis.x, original.paulis.x)
    np.testing.assert_array_equal(restored.paulis.z, original.paulis.z)
    assert restored.input_dims() == (4,)
    assert restored.output_dims() == (2, 2)
    assert restored.qargs == (7,)
    np.testing.assert_array_equal(restored.to_matrix(), original.to_matrix())


def test_sparse_symbolic_coefficients_preserve_shared_parameter_identity():
    theta = Parameter("theta")
    original = SparsePauliOp(["XI", "IZ"], np.array([theta, 2 * theta], dtype=object))
    restored = decode(encode(original))
    assert restored.coeffs.dtype == object
    assert restored.parameters == original.parameters
    np.testing.assert_array_equal(
        restored.assign_parameters({theta: 0.75}).to_matrix(),
        original.assign_parameters({theta: 0.75}).to_matrix(),
    )


@pytest.mark.parametrize("mutation", ["phase", "coefficients", "dimensions", "qargs"])
def test_malformed_sparse_operator_is_rejected(mutation):
    from graybench.circuit_wire import WireError
    from graybench.scientific_wire import array_record

    wire = encode(SparsePauliOp(["XI", "IZ"], [1, 2]))
    if mutation == "phase":
        wire["phase"] = array_record(np.array([0, 4], dtype=np.int64))
    elif mutation == "coefficients":
        wire["coefficients"] = array_record(np.array([1], dtype=complex))
    elif mutation == "dimensions":
        wire["input_dims"] = [3]
    else:
        wire["qargs"] = ["0", "1"]
    with pytest.raises(WireError):
        decode(wire)


def test_scalar_coefficient_cannot_embed_nested_operator_constructors():
    from graybench.circuit_wire import WireError

    wire = encode(ScalarOp(2, 1))
    wire["coefficient"] = encode(ScalarOp(2, 2))
    with pytest.raises(WireError, match="coefficient representation"):
        decode(wire)


def test_sparse_nonfinite_coefficients_are_not_normalized_or_repaired():
    original = SparsePauliOp(["X", "Z"], [1, 1])
    original.coeffs[:] = [np.nan, np.inf]
    restored = decode(encode(original))
    assert restored.coeffs.dtype == original.coeffs.dtype
    assert restored.coeffs.tobytes() == original.coeffs.tobytes()


def test_empty_sparse_operator_retains_width_and_zero_terms():
    original = SparsePauliOp(["XI"])[[]]
    restored = decode(encode(original))
    assert restored.size == 0
    assert restored.num_qubits == 2
    assert restored.coeffs.shape == (0,)

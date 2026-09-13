import os

import pytest

from graybench.circuit_wire import WireError
from graybench.sandbox import Candidate
from graybench.value_wire import decode, encode

np = pytest.importorskip("numpy")
qi = pytest.importorskip("qiskit.quantum_info")


@pytest.mark.parametrize(
    "dtype",
    ["bool", "int8", "uint64", ">i4", "float16", "float32", ">f8", "complex64", "complex128"],
)
def test_array_roundtrip_preserves_dtype_shape_and_bytes(dtype):
    source = np.array([[0, 1], [1, 0]], dtype=dtype)
    restored = decode(encode(source))
    assert type(restored) is np.ndarray
    assert restored.dtype == source.dtype
    assert restored.shape == source.shape
    assert restored.tobytes() == source.tobytes()
    assert restored.flags.writeable


def test_complex_nonfinite_and_signed_zero_bits_are_preserved():
    source = np.array([complex(0.0, -0.0), complex(float("nan"), float("inf")), 2 + 3j])
    assert decode(encode(source)).tobytes() == source.tobytes()


@pytest.mark.parametrize(
    "source",
    [
        np.float64(0.5),
        np.int32(-5),
        np.complex64(1 + 2j),
        np.array(4.0),
        np.empty((0, 2)),
        np.arange(12).reshape(3, 4)[:, ::2],
    ],
)
def test_scalar_rank_zero_empty_and_noncontiguous_values(source):
    result = decode(encode(source))
    assert type(result) is type(source)
    assert result.dtype == source.dtype
    assert result.shape == source.shape
    assert result.tobytes() == source.tobytes()


@pytest.mark.parametrize(
    "source",
    [
        qi.Statevector([1, 0, 0, 0, 0, 0], dims=(2, 3)),
        qi.DensityMatrix(np.eye(6) / 6, dims=(3, 2)),
        qi.Operator(np.arange(24).reshape(6, 4), input_dims=(2, 2), output_dims=(2, 3)),
    ],
)
def test_quantum_values_preserve_subsystem_dimensions(source):
    result = decode(encode(source))
    assert type(result) is type(source)
    assert result == source
    if isinstance(source, qi.Operator):
        assert result.input_dims() == source.input_dims()
        assert result.output_dims() == source.output_dims()
    else:
        assert result.dims() == source.dims()


@pytest.mark.parametrize("change", ["object", "allocation", "bytes", "base64", "shape"])
def test_untrusted_numeric_records_are_bounded(change):
    record = encode(np.array([1.0]))
    if change == "object":
        record["dtype"] = "|O"
    elif change == "allocation":
        record["shape"] = [100_000, 100_000]
    elif change == "bytes":
        record["bytes"] = ""
    elif change == "base64":
        record["bytes"] = "!" * len(record["bytes"])
    else:
        record["shape"] = [-1]
    with pytest.raises(WireError):
        decode(record)


def test_dimension_mismatch_is_not_silently_repaired():
    record = encode(qi.Statevector([1, 0]))
    record["dims"] = [3]
    with pytest.raises(WireError):
        decode(record)


def test_object_arrays_cannot_transport_executable_objects():
    with pytest.raises(WireError):
        encode(np.array([object()], dtype=object))


IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
docker_test = pytest.mark.skipif(not IMAGE, reason="Set immutable GRAYBENCH_TEST_IMAGE")


@docker_test
def test_statevector_crosses_candidate_boundary():
    code = """from qiskit.quantum_info import Statevector
from math import sqrt
def answer():
    return (Statevector.from_label('00') + Statevector.from_label('11')) / sqrt(2)
"""
    with Candidate(code, image=IMAGE, docker=DOCKER) as candidate:
        state = candidate.call("answer")
    assert type(state) is qi.Statevector
    assert state.equiv(qi.Statevector([1 / np.sqrt(2), 0, 0, 1 / np.sqrt(2)]))


@docker_test
def test_operator_input_and_output_cross_boundary():
    code = "def answer(op):\n    return op.adjoint()"
    source = qi.Operator([[0, 1j], [1, 0]])
    with Candidate(code, image=IMAGE, docker=DOCKER) as candidate:
        result = candidate.call("answer", source)
    assert result == source.adjoint()


@docker_test
def test_array_mutation_and_numpy_scalar_type_cross_boundary():
    code = "import numpy as np\ndef answer(a):\n    a[0]=3+4j\n    return np.float64(0.25)"
    with Candidate(code, image=IMAGE, docker=DOCKER) as candidate:
        result = candidate.call_with_updates("answer", np.zeros(3, dtype=complex))
    assert type(result.value) is np.float64
    assert result.value == 0.25
    assert result.args_after[0][0] == 3 + 4j

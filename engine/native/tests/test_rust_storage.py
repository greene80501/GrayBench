"""Required host controls for the experimental, instrumented Qiskit extension.

Invoke explicitly; stock Qiskit must fail rather than skip these controls.
GRAYBENCH_RUST_TEST_MODULE permits a separately compiled allocator harness,
whose results cannot establish that the actual Qiskit extension is instrumented.
"""

import gc
import importlib
import os
import weakref

import numpy as np
import pytest


@pytest.fixture
def native():
    module = importlib.import_module(
        os.environ.get("GRAYBENCH_RUST_TEST_MODULE", "qiskit._accelerate")
    )
    assert getattr(module, "_graybench_rust_storage_profile", None) == "rust-numpy-storage-v1"
    return module


def make(native, code="D", kind="vec", length=4, capacity=7):
    size = np.dtype(code).itemsize
    return native._graybench_rust_storage_new(
        code, kind, length * size, capacity * size, (length,), (size,), 0
    )


@pytest.mark.parametrize("code", list("fdFD"))
@pytest.mark.parametrize("kind", ["vec", "box"])
def test_numeric_allocator_identity_and_initialized_bytes(native, code, kind):
    capacity = 7 if kind == "vec" else 4
    root = make(native, code, kind, capacity=capacity)
    size = np.dtype(code).itemsize
    owner = root.base
    assert type(owner) is native._graybench_rust_storage_owner_type
    assert not root.flags.owndata
    descriptor = native._graybench_rust_storage_descriptor(owner)
    assert descriptor[:5] == (code, kind, 4 * size, capacity * size, 0)
    assert descriptor[5] is root
    data = np.arange(4, dtype=np.dtype(code)).tobytes()
    native._graybench_rust_storage_write(owner, data)
    np.testing.assert_array_equal(root, np.arange(4, dtype=np.dtype(code)))
    assert native._graybench_rust_storage_read(owner) == data
    assert len(native._graybench_rust_storage_read(owner)) == 4 * size
    with pytest.raises(ValueError):
        native._graybench_rust_storage_write(owner, data + b"\x00" * size)


def test_owner_survives_root_without_cycle(native):
    root = make(native)
    owner = root.base
    observed = weakref.ref(root)
    del root
    gc.collect()
    assert observed() is None
    assert native._graybench_rust_storage_descriptor(owner)[5] is None
    assert native._graybench_rust_storage_read(owner) == bytes(64)
    native._graybench_rust_storage_write(owner, bytes(64))


def test_alias_mutation_negative_stride_and_readonly_root(native):
    root = make(native)
    root[:] = [1, 2, 3, 4]
    root.flags.writeable = False
    view = native._graybench_rust_storage_view(root, np.dtype("D"), (4,), (-16,), 48)
    assert view.base is root
    assert view.flags.writeable and not root.flags.writeable
    np.testing.assert_array_equal(view, [4, 3, 2, 1])
    view[0] = 9
    assert root[3] == 9
    native._graybench_rust_storage_write(root.base, np.array([6, 7, 8, 9], dtype="D").tobytes())
    np.testing.assert_array_equal(view, [9, 8, 7, 6])
    assert not root.flags.writeable


def test_offset_root_and_empty_overlap_geometry(native):
    root = native._graybench_rust_storage_new("d", "vec", 32, 64, (4,), (-8,), 24)
    assert native._graybench_rust_storage_descriptor(root.base)[4] == 24
    root[:] = [1, 2, 3, 4]
    view = native._graybench_rust_storage_view(root, np.dtype("d"), (3,), (0,), 8)
    np.testing.assert_array_equal(view, [3, 3, 3])
    view[1] = 10
    assert root[2] == 10
    empty = native._graybench_rust_storage_view(root, np.dtype("d"), (0,), (8,), 32)
    assert empty.size == 0 and empty.base is root


@pytest.mark.parametrize(
    "shape,strides,offset",
    [
        ((5,), (16,), 0),
        ((2,), (-16,), 0),
        ((1,), (16,), 64),
        ((0,), (16,), 65),
        ((2**63,), (16,), 0),
        ((2,), (2**63,), 0),
        ((1,) * 33, (0,) * 33, 0),
        ((4,), (16, 16), 0),
    ],
)
def test_invalid_alias_geometry_rejected(native, shape, strides, offset):
    root = make(native)
    with pytest.raises((ValueError, OverflowError)):
        native._graybench_rust_storage_view(root, np.dtype("D"), shape, strides, offset)
    assert len(native._graybench_rust_storage_read(root.base)) == 64


@pytest.mark.parametrize("dtype", [object, "V16", "U4", "S16", [("x", "f8")]])
def test_refcounted_or_structured_alias_dtype_rejected(native, dtype):
    root = make(native)
    with pytest.raises(TypeError):
        native._graybench_rust_storage_view(root, np.dtype(dtype), (1,), (16,), 0)


def test_fake_owner_and_unregistered_root_rejected(native):
    fake = type("PySliceContainer", (), {})()
    for value in (fake, object(), np.zeros(4), None):
        with pytest.raises(TypeError):
            native._graybench_rust_storage_descriptor(value)
        with pytest.raises(TypeError):
            native._graybench_rust_storage_read(value)
        with pytest.raises(TypeError):
            native._graybench_rust_storage_write(value, bytes(64))
    with pytest.raises(TypeError):
        native._graybench_rust_storage_view(np.zeros(4), np.dtype("D"), (1,), (16,), 0)


@pytest.mark.parametrize(
    "code,kind,length,capacity",
    [
        ("O", "vec", 64, 64),
        ("D", "fake", 64, 64),
        ("D", "vec", 64, 48),
        ("D", "box", 64, 80),
        ("D", "vec", 65, 80),
        ("D", "vec", 64, 81),
        ("D", "vec", 64, 16 * 1024 * 1024 + 16),
        ("D", "vec", -16, 64),
    ],
)
def test_invalid_allocation_rejected(native, code, kind, length, capacity):
    with pytest.raises((TypeError, ValueError, OverflowError)):
        native._graybench_rust_storage_new(code, kind, length, capacity, (4,), (16,), 0)


def test_empty_allocation_and_repeated_lifetime(native):
    for _ in range(200):
        root = make(native, length=0, capacity=0)
        assert native._graybench_rust_storage_read(root.base) == b""
        assert native._graybench_rust_storage_descriptor(root.base)[:5] == ("D", "vec", 0, 0, 0)
        native._graybench_rust_storage_write(root.base, b"")
        del root
    gc.collect()


def test_real_qiskit_pauli_matrix_registered(native):
    if os.environ.get("GRAYBENCH_RUST_TEST_MODULE"):
        pytest.skip("Allocator harness cannot qualify actual Qiskit storage")
    from qiskit.quantum_info import SparsePauliOp

    matrix = SparsePauliOp("XYZ").to_matrix()
    root = matrix
    while isinstance(root.base, np.ndarray):
        root = root.base
    descriptor = native._graybench_rust_storage_descriptor(root.base)
    assert descriptor[0] == "D" and descriptor[2] == matrix.nbytes
    assert descriptor[5] is root
    # Separate literal tensor product checks arithmetic, including imaginary Y.
    x = np.array([[0, 1], [1, 0]], dtype=complex)
    y = np.array([[0, -1j], [1j, 0]], dtype=complex)
    z = np.diag([1, -1])
    np.testing.assert_array_equal(matrix, np.kron(np.kron(x, y), z))

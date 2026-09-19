import numpy as np
import pytest

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="geometry", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, seq=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=seq), sequence=seq))["value"]


@pytest.mark.parametrize("dtype", [np.int64, object])
def test_owner_reshape_preserves_object_and_held_view(dtype):
    a, b = arenas()
    owner = np.array([1, 2, 3, 4, 5, 6], dtype=dtype)
    view = owner[1:5]
    remote, held = transfer(a, b, (owner, view))
    remote.shape = (2, 3)
    transfer(b, a, remote)
    assert owner.shape == (2, 3) and view.base is owner
    assert view.shape == (4,) and held.base is remote
    np.testing.assert_array_equal(owner, [[1, 2, 3], [4, 5, 6]])
    assert transfer(a, b, owner, 2) is remote


@pytest.mark.parametrize("dtype", [np.int64, object])
def test_fortran_owner_layout_change_preserves_raw_storage(dtype):
    a, b = arenas()
    owner = np.array([[1, 2, 3], [4, 5, 6]], dtype=dtype, order="F")
    remote = transfer(a, b, owner)
    remote.strides = (3 * remote.itemsize, remote.itemsize)
    remote.shape = (3, 2)
    expected = remote.copy()
    transfer(b, a, remote)
    assert owner.flags.owndata
    np.testing.assert_array_equal(owner, expected)
    assert owner.strides == remote.strides


@pytest.mark.parametrize("dtype", [np.int64, object])
def test_view_reshape_negative_and_zero_stride_updates(dtype):
    a, b = arenas()
    owner = np.array([1, 2, 3, 4, 5, 6], dtype=dtype)
    view = owner[::-1]
    remote, storage = transfer(a, b, (view, owner))
    remote.shape = (2, 3)
    transfer(b, a, remote)
    assert view.shape == (2, 3) and view.strides == (-3 * view.itemsize, -view.itemsize)
    assert view.base is owner
    remote.strides = (0, 0)
    transfer(b, a, remote, 2)
    assert view.strides == (0, 0) and view[0, 0] == 6


@pytest.mark.parametrize("destination", ["<u1", "<i4", ">f8"])
def test_owner_dtype_reinterpretation_keeps_buffer_and_existing_view(destination):
    a, b = arenas()
    owner = np.arange(8, dtype="<u8")
    view = owner[1:3]
    remote, held = transfer(a, b, (owner, view))
    remote.dtype = np.dtype(destination)
    expected = remote.copy()
    transfer(b, a, remote)
    assert owner.dtype == np.dtype(destination) and owner.shape == remote.shape
    assert view.dtype == np.dtype("<u8") and view.base is owner
    np.testing.assert_array_equal(owner, expected)
    np.testing.assert_array_equal(view, [1, 2])


@pytest.mark.parametrize("dtype", ["<u1", "<u4", ">u8"])
def test_view_dtype_change_with_noncontiguous_outer_dimension(dtype):
    a, b = arenas()
    owner = np.arange(24, dtype="<u4")
    view = owner.reshape(6, 4)[::-2]
    remote, storage = transfer(a, b, (view, owner))
    remote.dtype = np.dtype(dtype)
    expected = remote.copy()
    transfer(b, a, remote)
    assert view.dtype == remote.dtype and view.shape == remote.shape
    assert view.strides == remote.strides and view.base is owner
    np.testing.assert_array_equal(view, expected)


@pytest.mark.parametrize("dtype", [np.int64, object])
def test_empty_shape_changes(dtype):
    a, b = arenas()
    owner = np.empty((2, 0), dtype=dtype)
    remote = transfer(a, b, owner)
    remote.shape = (0, 3, 1)
    transfer(b, a, remote)
    assert owner.shape == (0, 3, 1)


def test_forged_geometry_update_fails_before_existing_values_change():
    a, b = arenas()
    owner = np.arange(4, dtype=np.int64)
    held = transfer(a, b, owner)
    owner[0] = 19
    wire = a.snapshot({"value": owner}, sequence=2)
    wire["nodes"][0]["state"]["strides"] = [10000]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    np.testing.assert_array_equal(held, np.arange(4))


def test_storage_resize_remains_unsupported_before_mutation():
    import base64

    a, b = arenas()
    owner = np.arange(6, dtype=np.int64)
    remote = transfer(a, b, owner)
    wire = a.snapshot({"value": owner}, sequence=2)
    state = wire["nodes"][0]["state"]
    state["shape"] = [8]
    state["bytes"] = base64.b64encode(np.arange(8, dtype=np.int64).tobytes()).decode()
    with pytest.raises(WireError, match="resizing"):
        b.prepare(wire, sequence=2)
    assert remote.shape == (6,)
    np.testing.assert_array_equal(remote, owner)


@pytest.mark.parametrize("dtype", [np.int64, object])
def test_readonly_owner_geometry_changes_preserve_readonly_flag(dtype):
    a, b = arenas()
    owner = np.array([1, 2, 3, 4], dtype=dtype)
    owner.flags.writeable = False
    remote = transfer(a, b, owner)
    remote.shape = (2, 2)
    transfer(b, a, remote)
    assert owner.shape == (2, 2) and not owner.flags.writeable


def test_rejected_late_update_keeps_existing_array_metadata():
    a, b = arenas()
    owner = np.arange(6, dtype=np.int64)
    remote = transfer(a, b, owner)
    owner.shape = (2, 3)
    wire = a.snapshot({"value": (owner, [1])}, sequence=2)
    next(n for n in wire["nodes"] if n["kind"] == "list")["state"] = [{"ref": "j:999"}]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert remote.shape == (6,) and remote.strides == (8,)
    np.testing.assert_array_equal(remote, np.arange(6))


def test_broadcast_view_dtype_change_and_shape_keep_offset_and_storage():
    a, b = arenas()
    owner = np.arange(8, dtype=np.uint8)
    view = np.ndarray((3, 4), dtype=np.uint8, buffer=owner, offset=2, strides=(0, 1))
    remote = transfer(a, b, view)
    remote.dtype = np.dtype("<u2")
    expected = remote.copy()
    transfer(b, a, remote)
    assert view.shape == (3, 2) and view.strides == (0, 2) and view.base is owner
    np.testing.assert_array_equal(view, expected)

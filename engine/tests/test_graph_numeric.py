import copy

import numpy as np
import pytest

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas(**limits):
    return tuple(
        GraphArena(side=side, session="numeric", limits=GraphLimits(**limits))
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    return receiver.commit(
        receiver.prepare(sender.snapshot({"value": value}, sequence=sequence), sequence=sequence)
    )["value"]


def test_overlapping_views_share_original_owner_and_updates_return_in_place():
    judge, worker = arenas()
    backing = np.arange(12, dtype=np.float64)
    left, right = backing[1:8], backing[3:10]
    remote_left, remote_right, remote_backing = transfer(judge, worker, (left, right, backing))
    assert remote_left.base is remote_backing
    assert remote_right.base is remote_backing
    assert np.shares_memory(remote_left, remote_right)
    remote_left[2] = 91
    assert remote_right[0] == 91
    result = transfer(worker, judge, remote_right)
    assert result is right
    assert right[0] == left[2] == backing[3] == 91


@pytest.mark.parametrize("order", ["C", "F"])
def test_transposes_negative_and_zero_strides_preserve_storage(order):
    sender, receiver = arenas()
    backing = np.array([[1, 2, 3], [4, 5, 6]], dtype=">i4", order=order)
    reverse = backing[::-1, ::-1]
    broadcast = np.broadcast_to(backing[0, :1], (4,))
    a, transpose, b, c = transfer(sender, receiver, (backing, backing.T, reverse, broadcast))
    assert a.flags.owndata and a.base is None
    for original, actual in zip((backing.T, reverse, broadcast), (transpose, b, c), strict=True):
        assert actual.strides == original.strides
        assert actual.dtype.str == ">i4"
        assert actual.base is a
        np.testing.assert_array_equal(actual, original)
    b[0, 0] = 99
    assert a[1, 2] == transpose[2, 1] == 99
    assert not c.flags.writeable
    with pytest.raises(ValueError):
        c[0] = 2


def test_equal_arrays_remain_disjoint_and_readonly_owner_keeps_writable_held_view():
    judge, worker = arenas()
    a = np.arange(4, dtype=np.int32)
    b = a.copy()
    held = a[:]
    a.flags.writeable = False
    x, y, view = transfer(judge, worker, (a, b, held))
    assert not np.shares_memory(x, y)
    assert not x.flags.writeable and view.flags.writeable
    view[1] = 17
    transfer(worker, judge, (x, y, view))
    assert a[1] == 17 and b[1] == 1
    assert not a.flags.writeable and held.flags.writeable


@pytest.mark.parametrize("shape", [(), (0,), (2, 0, 3), (1, 3)])
def test_scalar_and_empty_array_shapes(shape):
    sender, receiver = arenas()
    a = np.zeros(shape, dtype=np.complex128, order="F")
    result = transfer(sender, receiver, a)
    assert result.shape == shape
    assert result.strides == a.strides
    assert result.flags.owndata
    assert result.tobytes() == a.tobytes()


def test_nonfinite_bytes_and_signed_zero_are_not_normalized():
    sender, receiver = arenas()
    a = np.array([0x8000000000000000, 0x7FF800000000002A, 0x7FF0000000000000], dtype="<u8")
    values = a.view("<f8")
    result = transfer(sender, receiver, values)
    assert result.tobytes() == bytes.fromhex("00000000000000802a0000000000f87f000000000000f07f")
    assert np.signbit(result[0]) and np.isnan(result[1]) and np.isinf(result[2])


def test_explicit_unaligned_flag_and_misaligned_views_are_preserved():
    sender, receiver = arenas()
    a = np.arange(20, dtype=np.uint8)
    view = np.ndarray((2,), dtype="<i4", buffer=a, offset=1)
    a.flags.aligned = False
    original, result = transfer(sender, receiver, (a, view))
    assert not original.flags.aligned and not result.flags.aligned
    assert result.base is original
    result[0] = 0x01020304
    assert original[1:5].tolist() == [4, 3, 2, 1]


def test_forged_alignment_is_rejected_before_other_changes():
    judge, worker = arenas()
    a = np.arange(20, dtype=np.uint8)
    owner, view = transfer(judge, worker, (a, np.ndarray((2,), dtype="i4", buffer=a, offset=1)))
    owner[0] = 99
    message = worker.snapshot({"value": view}, sequence=1)
    next(n for n in message["nodes"] if n["kind"] == "ndarray_view")["state"]["aligned"] = True
    with pytest.raises(WireError):
        judge.prepare(message, sequence=1)
    assert a[0] == 0


def test_geometry_changes_are_explicitly_unsupported_without_corrupting_aliases():
    judge, worker = arenas()
    a = np.arange(6)
    held = a[:]
    owner, view = transfer(judge, worker, (a, held))
    owner.shape = (2, 3)
    with pytest.raises(WireError, match="geometry"):
        worker.snapshot({"value": view}, sequence=1)
    assert a.shape == held.shape == (6,)


@pytest.mark.parametrize(
    "change", ["offset", "negative", "stride", "dtype", "dtype_char", "base", "bytes"]
)
def test_malformed_array_graph_rejected_before_mutation(change):
    judge, worker = arenas()
    original = np.arange(6, dtype=np.int32)
    remote = transfer(judge, worker, (original, original[1:]))
    remote[0][0] = 88
    message = worker.snapshot({"value": remote}, sequence=1)
    owner = next(n for n in message["nodes"] if n["kind"] == "ndarray_owner")
    view = next(n for n in message["nodes"] if n["kind"] == "ndarray_view")
    if change == "offset":
        view["state"]["offset"] = 1000
    elif change == "negative":
        view["state"]["offset"] = -1
    elif change == "stride":
        view["state"]["strides"] = [-100]
    elif change == "dtype":
        owner["state"]["dtype"] = "|O"
    elif change == "dtype_char":
        owner["state"]["dtype_char"] = "d"
    elif change == "base":
        view["state"]["base"] = {"ref": view["id"]}
    else:
        owner["state"]["bytes"] = ""
    with pytest.raises(WireError):
        judge.prepare(message, sequence=1)
    np.testing.assert_array_equal(original, [0, 1, 2, 3, 4, 5])


def test_array_byte_budget_counts_unique_storage_and_is_enforced_by_receiver():
    a = np.arange(8, dtype=np.uint8)
    sender, receiver = arenas(array_bytes=8)
    result = transfer(sender, receiver, (a, a[:], a[::-1]))
    assert result[1].base is result[2].base is result[0]
    sender, _ = arenas()
    _, receiver = arenas(array_bytes=7)
    wire = sender.snapshot({"value": a}, sequence=1)
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=1)
    sender, _ = arenas(array_bytes=8)
    with pytest.raises(WireError):
        sender.snapshot({"value": (a, a.copy())}, sequence=1)


def test_invalid_late_view_does_not_change_existing_readonly_flags():
    judge, worker = arenas()
    a = np.arange(5)
    a.flags.writeable = False
    remote = transfer(judge, worker, a)
    remote.flags.writeable = True
    remote[0] = 99
    message = worker.snapshot({"value": remote[::-1]}, sequence=1)
    bad = copy.deepcopy(message)
    next(n for n in bad["nodes"] if n["kind"] == "ndarray_view")["state"]["offset"] = 999
    with pytest.raises(WireError):
        judge.prepare(bad, sequence=1)
    assert not a.flags.writeable and a[0] == 0
    result = judge.commit(judge.prepare(message, sequence=1))["value"]
    assert result.base is a and a[0] == 99 and a.flags.writeable


@pytest.mark.parametrize(
    "array",
    [
        np.array([object()]),
        np.zeros(2, dtype=[("x", "i4")]),
        np.frombuffer(b"1234", dtype="u1"),
        np.zeros(2, dtype=np.dtype("i4", metadata={"unit": "m"})),
    ],
)
def test_unadmitted_storage_is_explicitly_unsupported(array):
    sender, _ = arenas()
    with pytest.raises(WireError):
        sender.snapshot({"value": array}, sequence=1)


@pytest.mark.parametrize(
    "value",
    [
        np.int8(-7),
        np.uint64(2**64 - 1),
        np.float32(-0.0),
        np.complex64(complex(float("nan"), 3)),
        np.bool_(True),
        np.intc(3),
        np.uintc(4),
    ],
)
def test_numpy_scalars_keep_type_bits_and_repeated_references(value):
    sender, receiver = arenas()
    first, second = transfer(sender, receiver, (value, value))
    assert type(first) is type(value)
    assert first.tobytes() == value.tobytes()
    assert first is second


def test_numpy_scalar_id_cannot_be_rewritten():
    judge, worker = arenas()
    value = np.int16(7)
    remote = transfer(judge, worker, value)
    wire = worker.snapshot({"value": remote}, sequence=1)
    wire["nodes"][0]["state"]["bytes"] = "CAA="
    with pytest.raises(WireError, match="immutable"):
        judge.prepare(wire, sequence=1)
    assert value == 7


@pytest.mark.parametrize("dtype", [np.intc, np.uintc])
def test_equal_width_distinct_numpy_c_types_keep_dtype_type(dtype):
    sender, receiver = arenas()
    value = np.array([1, 2, 3], dtype=dtype)
    result = transfer(sender, receiver, value)
    assert result.dtype.type is value.dtype.type
    assert type(result[0]) is type(value[0])

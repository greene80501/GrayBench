import copy

import numpy as np
import pytest
from qiskit.circuit import Parameter

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas(**limits):
    return tuple(
        GraphArena(side=side, session="object-storage", limits=GraphLimits(**limits))
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    return receiver.commit(
        receiver.prepare(sender.snapshot({"value": value}, sequence=sequence), sequence=sequence)
    )["value"]


def test_object_arrays_preserve_shared_parameter_and_nested_container_identity():
    sender, receiver = arenas()
    p, items = Parameter("p"), []
    a = np.empty(3, dtype=object)
    a[0], a[1], a[2] = p, p, items
    remote, parameter, child = transfer(sender, receiver, (a, p, items))
    assert remote[0] is remote[1] is parameter
    assert remote[2] is child
    child.append(parameter)
    assert transfer(receiver, sender, remote) is a
    assert items == [p] and items[0] is p


@pytest.mark.parametrize("order", ["C", "F"])
def test_object_views_preserve_overlaps_negative_strides_and_owner(order):
    sender, receiver = arenas()
    a = np.empty((2, 3), dtype=object, order=order)
    for i in range(6):
        a.flat[i] = [i]
    x, transposed, reversed_view, owner = transfer(
        sender, receiver, (a[:, 1:], a.T, a[::-1, ::-1], a)
    )
    assert x.base is owner and transposed.base is owner and reversed_view.base is owner
    assert owner.strides == a.strides and transposed.strides == a.T.strides
    replacement = []
    x[0, 0] = replacement
    assert transposed[1, 0] is replacement and reversed_view[1, 1] is replacement
    transfer(receiver, sender, owner)
    assert a[0, 1] == [] and a[0, 1] is not replacement


def test_object_array_self_cycle_and_tuple_cycle():
    sender, receiver = arenas()
    a = np.empty(2, dtype=object)
    t = (a,)
    a[0], a[1] = a, t
    result, other = transfer(sender, receiver, (a, t))
    assert result[0] is result and result[1] is other and other[0] is result


def test_readonly_owner_and_writable_held_object_view():
    sender, receiver = arenas()
    a = np.empty(2, dtype=object)
    a[:] = [1, 2]
    view = a[:]
    a.flags.writeable = False
    remote, held = transfer(sender, receiver, (a, view))
    assert not remote.flags.writeable and held.flags.writeable
    held[0] = [3]
    transfer(receiver, sender, remote)
    assert a[0] == [3] and not a.flags.writeable and view.flags.writeable


@pytest.mark.parametrize("shape", [(), (0,), (2, 0, 3)])
def test_object_empty_and_scalar_arrays(shape):
    sender, receiver = arenas()
    a = np.empty(shape, dtype=object)
    if a.size:
        a[()] = []
    result = transfer(sender, receiver, a)
    assert result.dtype == a.dtype and result.shape == shape and result.strides == a.strides
    if a.size:
        assert result[()] == []


def test_object_array_zero_stride_view():
    sender, receiver = arenas()
    a = np.empty(1, dtype=object)
    a[0] = []
    view = np.broadcast_to(a, (4,))
    actual, owner = transfer(sender, receiver, (view, a))
    assert actual.base is owner and not actual.flags.writeable
    assert actual.strides == (0,)
    assert all(item is owner[0] for item in actual)


def test_detached_object_array_item_updates_and_equal_replacement_stays_distinct():
    sender, receiver = arenas()
    old = []
    a = np.empty(1, dtype=object)
    a[0] = old
    remote, held = transfer(sender, receiver, (a, old))
    a[0] = []
    old.append(4)
    transfer(sender, receiver, a, sequence=2)
    assert remote[0] == [] and held == [4] and remote[0] is not held


def test_object_storage_budget_charges_owner_once_for_shared_views():
    a = np.empty(4, dtype=object)
    a[:] = [1, 2, 3, 4]
    sender, receiver = arenas(array_bytes=a.nbytes)
    assert transfer(sender, receiver, (a, a[:], a[::-1]))[0].tolist() == [1, 2, 3, 4]
    sender, receiver = arenas(array_bytes=a.nbytes - 1)
    with pytest.raises(WireError):
        sender.snapshot({"value": a}, sequence=1)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("offset", 1),
        ("offset", 1000),
        ("strides", [1]),
        ("strides", [-8]),
        ("shape", [10000]),
        ("base", {"ref": "j:999"}),
    ],
)
def test_forged_object_views_rejected_before_updates(field, bad):
    sender, receiver = arenas()
    a = np.empty(2, dtype=object)
    a[:] = [1, 2]
    result, _ = transfer(sender, receiver, (a, a[:]))
    a[0] = 3
    wire = sender.snapshot({"value": a}, sequence=2)
    next(n for n in wire["nodes"] if n["kind"] == "object_array_view")["state"][field] = bad
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=2)
    assert result.tolist() == [1, 2]


def test_new_object_view_misaligned_pointer_rejected():
    sender, receiver = arenas()
    a = np.empty(2, dtype=object)
    wire = sender.snapshot({"value": a[:]}, sequence=1)
    view = next(n for n in wire["nodes"] if n["kind"] == "object_array_view")
    view["state"]["offset"] = 1
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=1)


def test_object_owner_item_count_and_dangling_ref_validated_before_commit():
    sender, receiver = arenas()
    a = np.empty(2, dtype=object)
    a[:] = [1, 2]
    wire = sender.snapshot({"value": a}, sequence=1)
    for bad in ([], [1], [1, {"ref": "j:999"}]):
        attempt = copy.deepcopy(wire)
        attempt["nodes"][0]["state"]["items"] = bad
        with pytest.raises(WireError):
            receiver.prepare(attempt, sequence=1)


def test_false_alignment_flag_is_preserved_for_safe_object_storage():
    sender, receiver = arenas()
    a = np.empty(1, dtype=object)
    a[0] = []
    a.flags.aligned = False
    result = transfer(sender, receiver, a)
    assert not result.flags.aligned and result[0] == []


def test_databin_object_array_shape_and_alias():
    from qiskit.primitives import DataBin

    sender, receiver = arenas()
    a = np.empty(2, dtype=object)
    a[:] = [1, 2]
    data = DataBin(shape=(2,), observations=a)
    remote, array = transfer(sender, receiver, (data, a))
    assert remote.observations is array and remote.shape == (2,)


def test_databin_rejects_mismatched_object_array_shape():
    from qiskit.primitives import DataBin

    sender, _ = arenas()
    a = np.empty(2, dtype=object)
    data = DataBin(shape=(2,), observations=a)
    data._data["observations"] = np.empty(3, dtype=object)
    with pytest.raises(WireError):
        sender.snapshot({"value": data}, sequence=1)

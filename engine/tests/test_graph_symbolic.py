import copy
from uuid import UUID, SafeUUID

import pytest
from qiskit.circuit import Parameter, ParameterVector, ParameterVectorElement

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=side, session="symbols", limits=GraphLimits())
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    return receiver.commit(
        receiver.prepare(sender.snapshot({"value": value}, sequence=sequence), sequence=sequence)
    )["value"]


def test_equal_parameters_keep_distinct_objects_and_shared_references():
    sender, receiver = arenas()
    p = Parameter("p")
    q = Parameter("p", uuid=p.uuid)
    assert p == q and p is not q
    a, b, c = transfer(sender, receiver, (p, q, p))
    assert a == b == p and a is not b and a is c
    assert transfer(receiver, sender, a) is p


@pytest.mark.parametrize("safe", list(SafeUUID))
def test_uuid_objects_preserve_identity_and_safety(safe):
    sender, receiver = arenas()
    uid = UUID(int=17, is_safe=safe)
    equal = UUID(int=17, is_safe=safe)
    a, b, c = transfer(sender, receiver, (uid, equal, uid))
    assert a == b == uid and a is c and a is not b
    assert a.is_safe is safe


def test_vector_shrink_regrow_preserves_list_and_detached_equal_element():
    judge, worker = arenas()
    v = ParameterVector("theta", 3)
    held_list, held_element, uid = v.params, v[2], v._root_uuid
    remote, items, old, root = transfer(judge, worker, (v, held_list, held_element, uid))
    assert remote.params is items and items[2] is old
    assert old.vector is remote and remote._root_uuid is root
    remote.resize(1)
    result = transfer(worker, judge, remote)
    assert result is v and v.params is held_list and len(held_list) == 1
    assert held_element.vector is v and held_element.index == 2
    remote.resize(3)
    assert remote[2] == old and remote[2] is not old
    transfer(worker, judge, remote, sequence=2)
    assert v.params is held_list and v[2] == held_element and v[2] is not held_element
    assert v[2].vector is v and held_element.vector is v
    # Resnapshot must not create nodes for temporary UUID/property getter objects.
    before = len(judge.snapshot({"value": v}, sequence=2)["nodes"])
    after = len(judge.snapshot({"value": v}, sequence=3)["nodes"])
    assert before == after


def test_distinct_vectors_with_equal_root_uuid_do_not_collapse():
    sender, receiver = arenas()
    a, b = ParameterVector("v", 0), ParameterVector("v", 0)
    b._root_uuid = a._root_uuid
    a.resize(2)
    b.resize(2)
    x, y = transfer(sender, receiver, (a, b))
    assert x is not y and x.params is not y.params
    assert x[0] == y[0] and x[0] is not y[0]
    assert x[0].vector is x and y[0].vector is y
    assert x._root_uuid is y._root_uuid


def test_vector_element_arbitrary_explicit_uuid_preserved():
    sender, receiver = arenas()
    v = ParameterVector("v", 0)
    e = ParameterVectorElement(v, 12, uuid=UUID(int=43))
    remote, item = transfer(sender, receiver, (v, e))
    assert len(remote) == 0 and item.index == 12 and item.uuid.int == 43
    assert item.vector is remote and item.name == "v[12]"


@pytest.mark.parametrize(
    "field,bad",
    [
        ("uuid", "bad"),
        ("uuid", 3),
        ("name", False),
    ],
)
def test_late_malformed_parameter_rejects_without_mutating_exported_list(field, bad):
    sender, receiver = arenas()
    values, p = [1], Parameter("p")
    remote, _ = transfer(sender, receiver, (values, p))
    values.append(2)
    wire = sender.snapshot({"value": (values, p)}, sequence=2)
    target = next(n for n in wire["nodes"] if n["kind"] == "parameter")
    target["state"][field] = bad
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=2)
    assert remote == [1]


def test_vector_replaced_parameter_list_preserves_old_list_alias():
    sender, receiver = arenas()
    v = ParameterVector("v", 1)
    old = v.params
    remote, held = transfer(sender, receiver, (v, old))
    v._params = list(old)
    transfer(sender, receiver, v, sequence=2)
    assert remote.params is not held and remote.params[0] is held[0]


def test_parameter_immutable_record_cannot_be_rewritten():
    sender, receiver = arenas()
    wire = sender.snapshot({"value": Parameter("p")}, sequence=1)
    receiver.commit(receiver.prepare(wire, sequence=1))
    bad = copy.deepcopy(wire)
    bad["sequence"] = 2
    bad["nodes"][0]["state"]["name"] = "q"
    with pytest.raises(WireError):
        receiver.prepare(bad, sequence=2)


@pytest.mark.parametrize(
    "kind,field,bad",
    [
        ("parameter", "name", "\ud800"),
        ("parameter_vector", "params", {"ref": "j:999"}),
        ("parameter_vector", "root_uuid", 4),
        ("parameter_vector_element", "index", True),
        ("parameter_vector_element", "index", 4096),
        ("parameter_vector_element", "name", "other"),
        ("uuid", "safe", "__dict__"),
        ("uuid", "uuid", "00000000-0000-0000-0000-00000000000A"),
    ],
)
def test_malformed_symbol_records_fail_before_existing_mutation(kind, field, bad):
    sender, receiver = arenas()
    v, values, p = ParameterVector("v", 1), [1], Parameter("p")
    _, held, _ = transfer(sender, receiver, (v, values, p))
    values.append(2)
    wire = sender.snapshot({"value": v}, sequence=2)
    next(n for n in wire["nodes"] if n["kind"] == kind)["state"][field] = bad
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=2)
    assert held == [1]


def test_exported_vector_rename_fails_without_advancing_snapshot():
    sender, receiver = arenas()
    v = ParameterVector("v", 0)
    remote = transfer(sender, receiver, v)
    v._name = "new"
    with pytest.raises(WireError, match="rename"):
        sender.snapshot({"value": v}, sequence=2)
    v._name = "v"
    assert transfer(sender, receiver, v, sequence=2) is remote


def test_empty_parameter_name_matches_native_sdk():
    sender, receiver = arenas()
    p = Parameter("")
    result = transfer(sender, receiver, p)
    assert result == p and result.name == ""


def test_new_parameter_with_non_utf8_name_is_wire_error():
    sender, receiver = arenas()
    wire = sender.snapshot({"value": Parameter("p")}, sequence=1)
    wire["nodes"][0]["state"]["name"] = "\ud800"
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=1)

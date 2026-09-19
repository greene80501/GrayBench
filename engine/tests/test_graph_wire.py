import copy

import pytest
from qiskit.transpiler import PropertySet

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas(**limits):
    options = GraphLimits(**limits)
    return (
        GraphArena(side="judge", session="test", limits=options),
        GraphArena(side="candidate", session="test", limits=options),
    )


def transfer(sender, receiver, roots, sequence):
    return receiver.commit(
        receiver.prepare(sender.snapshot(roots, sequence=sequence), sequence=sequence)
    )


def test_shared_positional_keyword_object_and_equal_distinct_values():
    sender, receiver = arenas()
    shared = []
    other = []
    roots = transfer(sender, receiver, {"args": (shared, other), "kwargs": {"b": shared}}, 1)
    assert roots["args"][0] is roots["kwargs"]["b"]
    assert roots["args"][0] is not roots["args"][1]


def test_cycles_and_tuple_dependencies_roundtrip():
    sender, receiver = arenas()
    items = []
    pair = (items,)
    mapping = {"pair": pair, "self": items}
    items.extend((pair, mapping, items))
    result = transfer(sender, receiver, {"value": pair}, 1)["value"]
    assert result[0][0] is result
    assert result[0][1]["self"] is result[0]
    assert result[0][2] is result[0]


def test_response_resolves_original_input_and_applies_mutation():
    judge, worker = arenas()
    original = []
    received = transfer(judge, worker, {"args": (original,)}, 1)["args"][0]
    received.append(7)
    result = transfer(worker, judge, {"value": received}, 1)["value"]
    assert result is original
    assert original == [7]


def test_equal_replacement_and_detached_child_updates_across_calls():
    judge, worker = arenas()
    child = []
    original = [child]
    remote = transfer(judge, worker, {"value": original}, 1)["value"]
    old_remote_child = remote[0]
    remote[0] = []
    transfer(worker, judge, {"value": remote}, 1)
    assert original[0] is not child
    again = transfer(judge, worker, {"unrelated": 3}, 2)
    assert again["unrelated"] == 3
    old_remote_child.append(9)
    transfer(worker, judge, {"value": None}, 2)
    assert child == [9]


def test_property_set_type_order_and_missing_lookup():
    a, b = arenas()
    original = PropertySet(second=2, first=1)
    result = transfer(a, b, {"value": original}, 1)["value"]
    assert type(result) is PropertySet
    assert list(result.items()) == [("second", 2), ("first", 1)]
    assert result["absent"] is None and "absent" not in result


@pytest.mark.parametrize(
    "change",
    [
        "dangling",
        "duplicate",
        "kind",
        "session",
        "ownership",
        "boolean_id",
        "bad_key",
        "missing_existing",
    ],
)
def test_bad_snapshot_preparation_is_nonmutating(change):
    a, b = arenas()
    original = [1]
    remote = transfer(a, b, {"value": original}, 1)["value"]
    remote[:] = [2]
    wire = b.snapshot({"value": remote}, sequence=1)
    if change == "dangling":
        wire["roots"]["bad"] = {"ref": "c:999"}
    elif change == "duplicate":
        wire["nodes"].append(copy.deepcopy(wire["nodes"][0]))
    elif change == "kind":
        wire["nodes"][0]["kind"] = "unsafe"
    elif change == "session":
        wire["session"] = "other"
    elif change == "ownership":
        wire["nodes"].append({"id": "j:99", "kind": "list", "state": []})
    elif change == "boolean_id":
        wire["nodes"][0]["id"] = True
    elif change == "bad_key":
        wire["nodes"].append(
            {"id": "c:99", "kind": "dict", "state": [[{"ref": wire["nodes"][0]["id"]}, 3]]}
        )
    else:
        wire["nodes"] = []
    with pytest.raises(WireError):
        a.prepare(wire, sequence=1)
    assert original == [1]


def test_reused_foreign_and_stale_preparations_fail():
    a, b = arenas()
    wire = a.snapshot({"value": [1]}, sequence=1)
    first = b.prepare(wire, sequence=1)
    second = b.prepare(wire, sequence=1)
    with pytest.raises(WireError):
        a.commit(first)
    assert b.commit(first)["value"] == [1]
    for plan in (first, second):
        with pytest.raises(WireError):
            b.commit(plan)
    with pytest.raises(WireError):
        b.prepare(wire, sequence=1)


def test_preparation_owns_wire_data_and_does_not_apply_until_commit():
    a, b = arenas()
    value = [1]
    remote = transfer(a, b, {"value": value}, 1)["value"]
    remote[:] = [2]
    wire = b.snapshot({"value": remote}, sequence=1)
    plan = a.prepare(wire, sequence=1)
    assert value == [1]
    wire["nodes"][0]["state"] = [99]
    assert a.commit(plan)["value"] is value
    assert value == [2]


def test_existing_tuple_cannot_be_rewritten():
    a, b = arenas()
    value = (1,)
    remote = transfer(a, b, {"value": value}, 1)["value"]
    wire = b.snapshot({"value": remote}, sequence=1)
    wire["nodes"][0]["state"] = [1.0]
    with pytest.raises(WireError):
        a.prepare(wire, sequence=1)
    assert type(value[0]) is int


@pytest.mark.parametrize(
    "limit,roots",
    [
        ("nodes", {"value": [[], []]}),
        ("edges", {"value": [1, 2, 3]}),
        ("message_bytes", {"value": "x" * 100}),
        ("depth", {"value": [[[[]]]]}),
    ],
)
def test_limits_and_failed_snapshot_do_not_poison_arena(limit, roots):
    a, b = arenas(**{limit: 2 if limit != "message_bytes" else 120})
    with pytest.raises(WireError):
        a.snapshot(roots, sequence=1)
    result = transfer(a, b, {"value": None}, 1)
    assert result == {"value": None}


def test_closed_arena_rejects_further_calls():
    a, _ = arenas()
    a.close()
    with pytest.raises(WireError):
        a.snapshot({"value": []}, sequence=1)


def test_receiver_enforces_graph_depth_independently_of_sender():
    sender, _ = arenas()
    receiver = GraphArena(side="candidate", session="test", limits=GraphLimits(depth=2))
    wire = sender.snapshot({"value": [[[[]]]]}, sequence=1)
    with pytest.raises(WireError, match="nesting"):
        receiver.prepare(wire, sequence=1)


def test_cross_call_identity_and_incorrect_identity_function():
    a, b = arenas()
    shared = []
    args = transfer(a, b, {"args": (shared, shared)}, 1)["args"]
    saved = args[0]
    wrong = args[0] is not args[1]
    assert transfer(b, a, {"value": wrong}, 1)["value"] is False
    args = transfer(a, b, {"args": (shared,)}, 2)["args"]
    assert args[0] is saved


@pytest.mark.parametrize("case", ["tuple_cycle", "duplicate_key", "type_change", "noncanonical_id"])
def test_graph_rejects_invalid_identity_structures(case):
    a, b = arenas()
    remote = transfer(a, b, {"value": [1]}, 1)["value"]
    wire = b.snapshot({"value": remote}, sequence=1)
    if case == "tuple_cycle":
        wire["nodes"].append({"id": "c:9", "kind": "tuple", "state": [{"ref": "c:9"}]})
    elif case == "duplicate_key":
        wire["nodes"].append({"id": "c:9", "kind": "dict", "state": [[1, 3], [True, 4]]})
    elif case == "type_change":
        wire["nodes"][0]["kind"] = "dict"
        wire["nodes"][0]["state"] = []
    else:
        wire["nodes"].append({"id": "c:09", "kind": "list", "state": []})
    with pytest.raises(WireError):
        a.prepare(wire, sequence=1)


def test_node_limit_counts_detached_retained_objects():
    a, b = arenas(nodes=2)
    transfer(a, b, {"value": [[]]}, 1)
    with pytest.raises(WireError, match="node limit"):
        a.snapshot({"value": []}, sequence=2)


def test_unexpected_apply_failure_closes_arena(monkeypatch):
    from graybench.graph_types import ContainerCodec

    a, b = arenas()
    plan = b.prepare(a.snapshot({"value": [1]}, sequence=1), sequence=1)

    def broken_apply(self, target, state):
        raise RuntimeError("unexpected apply failure")

    monkeypatch.setattr(ContainerCodec, "apply", broken_apply)
    with pytest.raises(RuntimeError, match="apply failure"):
        b.commit(plan)
    with pytest.raises(WireError, match="closed"):
        b.snapshot({"value": []}, sequence=1)


@pytest.mark.parametrize(
    "options,roots",
    [
        ({"nodes": 1}, {"value": [[]]}),
        ({"edges": 2}, {"value": [1, 2, 3]}),
        ({"message_bytes": 120}, {"value": "x" * 200}),
    ],
)
def test_receiver_enforces_its_own_allocation_limits(options, roots):
    sender, _ = arenas()
    receiver = GraphArena(side="candidate", session="test", limits=GraphLimits(**options))
    wire = sender.snapshot(roots, sequence=1)
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=1)


def test_snapshot_records_do_not_expose_mutable_immutable_history():
    sender, receiver = arenas()
    original = (1,)
    wire = sender.snapshot({"value": original}, sequence=1)
    wire["nodes"][0]["state"] = [2]
    remote = receiver.commit(receiver.prepare(wire, sequence=1))["value"]
    assert remote == (2,)
    with pytest.raises(WireError, match="immutable"):
        sender.prepare(receiver.snapshot({"value": remote}, sequence=1), sequence=1)
    assert original == (1,)

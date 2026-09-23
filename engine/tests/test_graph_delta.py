"""Delta transport must preserve full graph semantics and transactional rejection."""

import copy
import hashlib

import pytest

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_wire import GraphArena, GraphLimits, wire_bytes


def pair(*, wire_limit=100000, state_limit=100000):
    from graybench.graph_delta import DeltaGraphArena

    anchors = PublicAnchorRegistry.capture()
    return tuple(
        DeltaGraphArena(
            GraphArena(
                side=side,
                session="delta-test",
                limits=GraphLimits(message_bytes=state_limit),
                anchors=anchors,
            ),
            wire_limit=wire_limit,
        )
        for side in ("judge", "candidate")
    )


def receive(arena, frame, sequence):
    return arena.commit(arena.prepare(frame, sequence=sequence))


def test_delta_retains_detached_alias_cycles_and_omits_unchanged_records():
    judge, candidate = pair()
    held = []
    held.append(held)
    first = judge.snapshot({"value": held, "large": ["x" * 10000]}, sequence=1)
    remote = receive(candidate, first, 1)
    assert remote["value"][0] is remote["value"]
    response = candidate.snapshot({"result": remote["value"]}, sequence=1)
    assert response["nodes"] == []
    assert len(wire_bytes(response)) < 1000
    assert receive(judge, response, 1)["result"] is held
    held.append(7)
    second = judge.snapshot({"value": None}, sequence=2)
    assert len(second["nodes"]) == 1
    receive(candidate, second, 2)
    assert remote["value"][1] == 7  # Detached from current roots, still observable.
    remote["value"].append(9)
    receive(judge, candidate.snapshot({"result": None}, sequence=2), 2)
    assert held[0] is held and held[1:] == [7, 9]


@pytest.mark.parametrize(
    "fault", ["base", "digest", "side", "session", "sequence", "duplicate", "missing"]
)
def test_bad_frame_does_not_advance_base_or_mutate_objects(fault):
    judge, candidate = pair()
    held = [1]
    receive(candidate, judge.snapshot({"value": held}, sequence=1), 1)
    good = candidate.snapshot({"result": [2]}, sequence=1)
    bad = copy.deepcopy(good)
    if fault in ("base", "digest"):
        bad[fault] = "0" * 64
    elif fault == "side":
        bad["side"] = "judge"
    elif fault == "session":
        bad["session"] = "another-session"
    elif fault == "sequence":
        bad["sequence"] = True
    elif fault == "duplicate":
        bad["nodes"].append(copy.deepcopy(bad["nodes"][0]))
    else:
        bad["nodes"].clear()
    with pytest.raises(WireError):
        judge.prepare(bad, sequence=1)
    assert held == [1]
    assert receive(judge, good, 1)["result"] == [2]


def test_prepared_frame_is_independent_and_cannot_be_replayed():
    judge, candidate = pair()
    frame = judge.snapshot({"value": [1]}, sequence=1)
    prepared = candidate.prepare(frame, sequence=1)
    frame["nodes"].clear()
    view = prepared.snapshot
    view["nodes"].clear()
    assert candidate.commit(prepared)["value"] == [1]
    with pytest.raises(WireError):
        candidate.commit(prepared)
    other, _ = pair()
    with pytest.raises(WireError):
        other.commit(prepared)


def test_live_mutation_after_prepare_closes_session_without_advancing_delta_base():
    judge, candidate = pair()
    held = [1]
    remote = receive(candidate, judge.snapshot({"value": held}, sequence=1), 1)
    remote["value"].append(2)
    prepared = judge.prepare(candidate.snapshot({"result": None}, sequence=1), sequence=1)
    held.append(3)
    with pytest.raises(WireError, match="changed after preparation"):
        judge.commit(prepared)
    assert held == [1, 3]
    with pytest.raises(WireError, match="closed"):
        judge.snapshot({"value": held}, sequence=2)


def test_expanded_state_limit_applies_to_small_incremental_frames():
    judge, _ = pair(state_limit=10000)
    _, candidate = pair(state_limit=1800)
    receive(candidate, judge.snapshot({"a": ["x" * 900]}, sequence=1), 1)
    receive(judge, candidate.snapshot({}, sequence=1), 1)
    frame = judge.snapshot({"b": ["y" * 900]}, sequence=2)
    assert len(wire_bytes(frame)) < 1800
    with pytest.raises(WireLimitError):
        candidate.prepare(frame, sequence=2)


def test_outbound_wire_limit_failure_is_fatal_after_snapshot():
    judge, _ = pair(wire_limit=600)
    with pytest.raises(WireLimitError):
        judge.snapshot({"value": ["x" * 1000]}, sequence=1)
    with pytest.raises(WireError, match="closed"):
        judge.snapshot({}, sequence=2)


@pytest.mark.parametrize("fault", ["local_id", "dangling", "kind", "anchor"])
def test_valid_hash_does_not_bypass_full_graph_validation(fault):
    judge, candidate = pair()
    good = judge.snapshot({"value": [1]}, sequence=1)
    bad = copy.deepcopy(good)
    node = bad["nodes"][0]
    if fault == "local_id":
        node["id"] = "c:0"
        bad["roots"]["value"] = {"ref": "c:0"}
    elif fault == "dangling":
        node["state"] = [{"ref": "j:99"}]
    elif fault == "kind":
        node["kind"] = "arbitrary_constructor"
    else:
        node["anchor"] = "not-a-public-anchor"
    expanded = {key: bad[key] for key in ("session", "sequence", "anchors", "roots", "nodes")}
    expanded["format"] = "call_graph_anchors_v1"
    bad["digest"] = hashlib.sha256(wire_bytes(expanded)).hexdigest()
    with pytest.raises(WireError):
        candidate.prepare(bad, sequence=1)
    assert receive(candidate, good, 1)["value"] == [1]

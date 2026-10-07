"""Commit must compare live identity as well as the prepared state bytes."""

import os

import pytest
from test_graph_bridge import task
from test_graph_delta import pair, receive

from graybench.circuit_wire import WireError
from graybench.upstream import UpstreamJudge


def test_equal_replacement_of_unexported_child_invalidates_preparation():
    judge, candidate = pair()
    held = [[]]
    original = held[0]
    receive(candidate, judge.snapshot({"value": held}, sequence=1), 1)
    frame = candidate.snapshot({"result": None}, sequence=1)
    held[0] = []  # A local-only child, assigned a supplemental capture ID.
    prepared = judge.prepare(frame, sequence=1)
    previous = held[0]
    held[0] = []  # Equal canonical capture, different actual object identity.
    with pytest.raises(WireError, match="changed after preparation"):
        judge.commit(prepared)
    assert held[0] == previous == original
    assert held[0] is not previous and held[0] is not original
    with pytest.raises(WireError, match="closed"):
        judge.snapshot({}, sequence=2)


def test_delta_closes_after_underlying_partial_live_apply(monkeypatch):
    from graybench.graph_types import ContainerCodec

    judge, candidate = pair()
    held = [1]
    remote = receive(candidate, judge.snapshot({"value": held}, sequence=1), 1)
    remote["value"].append(2)
    prepared = judge.prepare(candidate.snapshot({"result": None}, sequence=1), sequence=1)
    original = ContainerCodec.apply

    def fail_after_apply(self, target, value):
        original(self, target, value)
        raise RuntimeError("injected partial apply")

    monkeypatch.setattr(ContainerCodec, "apply", fail_after_apply)
    with pytest.raises(RuntimeError, match="injected partial apply"):
        judge.commit(prepared)
    assert held == [1, 2]
    with pytest.raises(WireError, match="closed"):
        judge.snapshot({}, sequence=2)
    with pytest.raises(WireError, match="closed"):
        judge.commit(prepared)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
@pytest.mark.parametrize("transport", ["snapshot-v1", "delta-v1"])
@pytest.mark.parametrize("change", ["value", "unsupported"])
def test_live_commit_state_change_is_infrastructure_even_if_test_catches_it(transport, change):
    test = """from graybench.graph_wire import GraphArena
original_commit = GraphArena.commit
held = [1]
def changed_commit(self, prepared):
    if self.side == 'judge': held.append(MUTATION)
    return original_commit(self, prepared)
GraphArena.commit = changed_commit
def check(candidate):
    try: candidate(held)
    except BaseException: pass
    assert True
""".replace("MUTATION", "99" if change == "value" else "object()")
    result = UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
        graph_transport=transport,
    ).evaluate(task(test), "def answer(value): return value")
    assert result.outcome == "infrastructure_error", result.evidence.get("detail")
    assert "Live anchor" in result.evidence["detail"]

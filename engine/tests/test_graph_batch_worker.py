"""The candidate worker owns the batch loop and validates before execution."""

import io
import json
import sys
from pathlib import Path

import pytest

from graybench import graph_worker
from graybench.circuit_wire import WireError
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_limits import GraphLimits, transport_record
from graybench.graph_wire import GraphArena


def test_positional_batch_calls_entry_point_in_order():
    seen = []

    def answer(value):
        seen.append(value)
        return value + 1

    assert graph_worker.execute_positional_batch(answer, (((1,), (2,), (3,)),), {}) == (
        2,
        3,
        4,
    )
    assert seen == [1, 2, 3]


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ((), {}),
        (((1,),), {}),
        (((),), {}),
        ((((1,), [2]),), {}),
        ((((1,),),), {"extra": True}),
        ((tuple((i,) for i in range(1025)),), {}),
    ],
)
def test_invalid_positional_batch_is_rejected_before_candidate_execution(args, kwargs):
    seen = []

    def answer(*values):
        seen.append(values)

    with pytest.raises(WireError):
        graph_worker.execute_positional_batch(answer, args, kwargs)
    assert seen == []


def test_later_candidate_exception_stops_batch():
    seen = []

    def answer(value):
        seen.append(value)
        if value == 2:
            raise ValueError("candidate fault")
        return value

    with pytest.raises(ValueError, match="candidate fault"):
        graph_worker.execute_positional_batch(answer, (((1,), (2,), (3,)),), {})
    assert seen == [1, 2]


@pytest.mark.parametrize("declared", (True, False))
def test_worker_batch_graph_envelope_requires_opt_in(tmp_path, monkeypatch, declared):
    session = "local-batch-envelope"
    registry = PublicAnchorRegistry.capture()
    limits = GraphLimits()
    judge_arena = GraphArena(side="judge", session=session, limits=limits, anchors=registry)
    graph = judge_arena.snapshot({"args": (((1,), (2,), (3,)),), "kwargs": {}}, sequence=1)
    config = {
        "session": session,
        "anchors": registry.manifest(),
        "limits": limits.record(),
        "transport": transport_record("snapshot-v1", limits.message_bytes),
        **({"graph_batch": "positional-batch-v1"} if declared else {}),
    }
    (tmp_path / "graph_config.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "candidate.py").write_text(
        "def answer(value): return value + 1\n", encoding="utf-8"
    )
    request = {
        "protocol": 4,
        "session": session,
        "sequence": 1,
        "entry_point": "answer",
        "graph": graph,
        "discard_result": False,
        "batch": True,
    }
    incoming = io.StringIO('{"protocol": 4, "start": true}\n' + json.dumps(request) + "\n")
    outgoing = io.StringIO()
    monkeypatch.setattr(graph_worker, "Path", lambda value: tmp_path / Path(value).name)
    monkeypatch.setattr(sys, "stdin", incoming)
    monkeypatch.setattr(sys, "stdout", outgoing)
    graph_worker.main()
    messages = [json.loads(line) for line in outgoing.getvalue().splitlines()]
    assert messages[0]["runtime_ready"] is True
    assert messages[1] == {"protocol": 4, "ready": True}
    response = messages[2]
    if not declared:
        assert response["error"] == "WireError"
        assert response["phase"] == "decoding"
        return
    assert response["exception"] is None
    roots = judge_arena.commit(judge_arena.prepare(response["graph"], sequence=1))
    assert roots["result"] == (2, 3, 4)

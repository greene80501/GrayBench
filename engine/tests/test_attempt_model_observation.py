"""Protocol 3.2 binds provider identity observations around each transport attempt."""

import httpx
import pytest

from graybench.campaign import GenerationRunner
from graybench.contracts import Generation
from graybench.ledger import StateError
from graybench.model_discovery import observe_run
from graybench.provenance import source_manifest
from graybench.providers import Ollama
from graybench.transport import Transport


def _protocol32(protocol):
    return protocol.model_copy(
        update={
            "schema_version": "3.2",
            "generation_code_digest": source_manifest()["digest"],
        }
    )


def _handler(calls, *, post_digest="a" * 64, post_status=200):
    discovery_count = 0

    def handle(request):
        nonlocal discovery_count
        path = request.url.path
        calls.append(path)
        if path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {"role": "assistant", "content": "def answer(x): return x + 1"},
                    "done": True,
                },
            )
        if path == "/api/version":
            discovery_count += 1
        if discovery_count == 2 and post_status != 200:
            return httpx.Response(post_status)
        if path == "/api/tags":
            digest = post_digest if discovery_count == 2 else "a" * 64
            return httpx.Response(200, json={"models": [{"name": "test-model", "digest": digest}]})
        if path == "/api/version":
            return httpx.Response(200, json={"version": "fixture"})
        if path == "/api/show":
            return httpx.Response(200, json={"model_info": {"architecture": "fixture"}})
        if path == "/api/ps":
            return httpx.Response(200, json={"models": []})
        raise AssertionError(path)

    return handle


def test_attempt_binds_pre_and_post_observations_in_wire_order(ledger, protocol, task):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    calls = []
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_handler(calls))) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(protocol.model, client=client)
        )
        assert runner.step()["delivery"] == "returned"
    assert calls == [
        "/api/version",
        "/api/tags",
        "/api/show",
        "/api/ps",
        "/api/chat",
        "/api/version",
        "/api/tags",
        "/api/show",
        "/api/ps",
    ]
    bindings = ledger.db.execute(
        "SELECT phase,observation_id FROM attempt_observations ORDER BY phase"
    ).fetchall()
    assert [(r["phase"], r["observation_id"]) for r in bindings] == [("post", 2), ("pre", 1)]
    assert ledger.attempt_observation_status(run)["status"] == "complete"
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.parametrize("post_digest,post_status", [("b" * 64, 200), ("a" * 64, 503)])
def test_post_discovery_problem_keeps_returned_answer_and_stops(
    ledger, protocol, task, post_digest, post_status
):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(
        transport=httpx.MockTransport(
            _handler([], post_digest=post_digest, post_status=post_status)
        )
    ) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(protocol.model, client=client)
        )
        assert runner.step()["reason"] == "model_discovery_unresolved"
    assert ledger.db.execute("SELECT count(*) FROM generations").fetchone()[0] == 1
    assert ledger.dispatch_state(ledger.samples(run)[0]["id"])["state"] == "returned"
    assert ledger.summary(run)["complete"] is False
    with pytest.raises(StateError, match="stable model observation"):
        ledger.judge(ledger.samples(run)[0]["id"], protocol.judge_digest, "pass", {})
    assert ledger.verify()["integrity"] == "verified"


def test_missing_post_after_durable_return_cannot_be_silently_reobserved(ledger, protocol, task):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_handler([]))) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, run, transport)
        attempt = ledger.begin_attempt(
            ledger.samples(run)[0]["id"], request, pre_observation_id=pre["observation_id"]
        )
        ledger.finish_attempt(
            attempt,
            "returned",
            {"simulated": "durably returned before post discovery"},
            200,
            Generation(
                text="answer",
                returned_model="test-model",
                response_id=None,
                finish_reason="stop",
                usage={},
            ),
        )
        runner = GenerationRunner(ledger, run, {protocol.task_keys[0]: request}, transport)
        assert runner.step() == {"state": "stopped", "reason": "model_post_observation_missing"}
        with pytest.raises(StateError, match="post-observation token"):
            observe_run(ledger, run, transport, attempt_id=attempt)
    assert ledger.attempt_observation_status(run)["status"] == "missing_post"
    assert ledger.summary(run)["pass_at_1"] is None
    with pytest.raises(StateError, match="model observation"):
        ledger.judge(ledger.samples(run)[0]["id"], protocol.judge_digest, "pass", {})
    assert ledger.verify()["integrity"] == "verified"


def test_post_binding_cannot_cross_runs(ledger, protocol, task):
    protocol = _protocol32(protocol)
    first, other = ledger.create_run(protocol), ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_handler([]))) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, first, transport)
        attempt = ledger.begin_attempt(
            ledger.samples(first)[0]["id"], request, pre_observation_id=pre["observation_id"]
        )
        ledger.finish_attempt(attempt, "rejected", {}, 429)
        with pytest.raises(StateError, match="different run"):
            observe_run(ledger, other, transport, attempt_id=attempt)
    assert ledger.attempt_observation_status(first)["status"] == "missing_post"
    assert ledger.verify()["integrity"] == "verified"


def test_unfinished_delivery_keeps_its_distinct_stop_reason(ledger, protocol, task):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_handler([]))) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, run, transport)
        ledger.begin_attempt(
            ledger.samples(run)[0]["id"], request, pre_observation_id=pre["observation_id"]
        )
        runner = GenerationRunner(ledger, run, {protocol.task_keys[0]: request}, transport)
        assert runner.step() == {"state": "stopped", "reason": "unresolved_delivery"}
    assert ledger.verify()["integrity"] == "verified"


def test_attempt_observation_binding_is_covered_by_event_integrity(ledger, protocol, task):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_handler([]))) as client:
        transport = Transport(protocol.model, client=client)
        runner = GenerationRunner(ledger, run, {protocol.task_keys[0]: request}, transport)
        assert runner.step()["delivery"] == "returned"
        observe_run(ledger, run, transport)
    ledger.db.execute("DROP TRIGGER immutable_attempt_observations_UPDATE")
    ledger.db.execute("UPDATE attempt_observations SET observation_id=3 WHERE phase='pre'")
    with pytest.raises(StateError, match="attempt_observations record"):
        ledger.verify()


def test_direct_protocol32_dispatch_needs_pre_observation(ledger, protocol, task):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with pytest.raises(StateError, match="pre-dispatch model observation"):
        ledger.begin_attempt(ledger.samples(run)[0]["id"], request)
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    assert "model_discovery_not_observed" in ledger.summary(run)["score_blockers"]


def test_intervening_discovery_cannot_replace_the_callers_pre_observation(ledger, protocol, task):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_handler([]))) as client:
        transport = Transport(protocol.model, client=client)
        first = observe_run(ledger, run, transport)
        second = observe_run(ledger, run, transport)
        sample = ledger.samples(run)[0]["id"]
        with pytest.raises(StateError, match="newer observation"):
            ledger.begin_attempt(sample, request, pre_observation_id=first["observation_id"])
        attempt = ledger.begin_attempt(sample, request, pre_observation_id=second["observation_id"])
    assert ledger.attempt_observation_status(run)["status"] == "missing_post"
    assert ledger.db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1
    assert attempt
    assert ledger.verify()["integrity"] == "verified"


def test_retry_binds_a_fresh_pair_of_observations(ledger, protocol, task):
    protocol = _protocol32(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    calls = []
    ordinary = _handler(calls)
    chat_count = 0

    def handle(http_request):
        nonlocal chat_count
        if http_request.url.path == "/api/chat":
            chat_count += 1
            if chat_count == 1:
                calls.append("/api/chat")
                return httpx.Response(429)
        return ordinary(http_request)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(protocol.model, client=client)
        )
        assert runner.step()["delivery"] == "rejected"
        assert runner.step()["delivery"] == "returned"
    assert chat_count == 2
    assert ledger.db.execute("SELECT count(*) FROM model_observations").fetchone()[0] == 4
    assert ledger.db.execute("SELECT count(*) FROM attempt_observations").fetchone()[0] == 4
    assert ledger.db.execute("SELECT count(*) FROM generations").fetchone()[0] == 1
    assert ledger.attempt_observation_status(run)["status"] == "complete"
    assert ledger.verify()["integrity"] == "verified"

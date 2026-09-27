"""Protocol 3.3 bounds the age of attempt-bound model metadata evidence."""

import contextlib
from datetime import datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

import graybench.ledger as ledger_module
from graybench.campaign import GenerationRunner
from graybench.campaign_setup import build_setup
from graybench.comparison import ComparisonPlan, validate_plan
from graybench.contracts import Generation, ModelObservationTiming, Protocol
from graybench.datasets import JudgeTask
from graybench.ledger import StateError
from graybench.model_discovery import observe_run
from graybench.provenance import source_manifest
from graybench.providers import Ollama
from graybench.transport import Transport


def _version(protocol):
    return protocol.model_copy(
        update={
            "schema_version": "3.3",
            "model_observation_timing": ModelObservationTiming(),
            "generation_code_digest": source_manifest()["digest"],
        }
    )


def _metadata(request):
    path = request.url.path
    if path == "/api/version":
        return httpx.Response(200, json={"version": "fixture"})
    if path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "test-model", "digest": "a" * 64}]})
    if path == "/api/show":
        return httpx.Response(200, json={"model_info": {"architecture": "fixture"}})
    if path == "/api/ps":
        return httpx.Response(200, json={"models": []})
    if path == "/api/chat":
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "message": {"role": "assistant", "content": "answer"},
                "done": True,
            },
        )
    raise AssertionError(path)


def test_timing_policy_is_frozen_only_in_protocol33(protocol, model, task):
    assert "model_observation_timing" not in protocol.model_dump(mode="json")
    with pytest.raises(ValidationError, match="model_observation_timing"):
        Protocol.model_validate({**protocol.model_dump(), "schema_version": "3.3"})
    with pytest.raises(ValidationError, match="model_observation_timing"):
        Protocol.model_validate(
            {
                **protocol.model_dump(),
                "model_observation_timing": ModelObservationTiming(),
            }
        )
    private = JudgeTask(
        public=task,
        canonical_solution="return x+1",
        upstream_test="def check(candidate):\n    assert candidate(1)==2",
        upstream_difficulty="fixture",
    )
    setup = build_setup("timed", model, (private,), "sha256:" + "0" * 64, protocol_version="3.3")
    assert setup.protocol.model_observation_timing == ModelObservationTiming()
    assert setup.protocol.schema_version == "3.3"
    with pytest.raises(ValidationError, match="greater than 0"):
        ModelObservationTiming(max_pre_age_seconds=0)
    with pytest.raises(ValidationError, match="finite"):
        ModelObservationTiming(max_post_delay_seconds=float("inf"))


def test_comparison_rejects_different_timing_bounds(protocol):
    left = _version(protocol)
    right = left.model_copy(
        update={"model_observation_timing": ModelObservationTiming(max_pre_age_seconds=45.0)}
    )
    plan = ComparisonPlan(
        left=left,
        right=right,
        families={left.task_keys[0]: "family"},
        seed=0,
        configuration_comparison="fixture",
        analysis_source=source_manifest()["digest"],
    )
    with pytest.raises(StateError, match="model_observation_timing"):
        validate_plan(plan)


def test_timely_pre_and_post_observations_complete(ledger, protocol, task):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(protocol.model, client=client)
        )
        assert runner.step()["delivery"] == "returned"
        assert runner.step() == {"state": "generation_complete", "reason": "all_returned"}
    timing = ledger.attempt_observation_status(run)
    assert timing["status"] == "complete"
    assert [gap["phase"] for gap in timing["timing_gaps"]] == [
        "pre",
        "delivery",
        "post",
        "post_commit",
        "post_confirmation",
    ]
    assert not timing["timing_violations"]
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.parametrize("offset", [31, -1])
def test_stale_or_future_pre_observation_stops_before_attempt(
    ledger, protocol, task, monkeypatch, offset
):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        pre = observe_run(ledger, run, Transport(protocol.model, client=client))
    recorded = ledger.db.execute("SELECT recorded_at FROM model_observations").fetchone()[0]
    shifted = datetime.fromisoformat(recorded) + timedelta(seconds=offset)
    monkeypatch.setattr(ledger_module, "now", lambda: shifted.isoformat())
    with pytest.raises(StateError, match="pre-observation timing"):
        ledger.begin_attempt(
            ledger.samples(run)[0]["id"],
            request,
            pre_observation_id=pre["observation_id"],
        )
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    assert ledger.verify()["integrity"] == "verified"


def test_slow_dispatch_commit_cannot_return_a_stale_pre_observation(
    ledger, protocol, task, monkeypatch
):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        pre = observe_run(ledger, run, Transport(protocol.model, client=client))
    recorded = datetime.fromisoformat(
        ledger.db.execute("SELECT recorded_at FROM model_observations").fetchone()[0]
    )
    clock = [recorded + timedelta(seconds=1)]
    monkeypatch.setattr(ledger_module, "now", lambda: clock[0].isoformat())
    original_transaction = ledger.transaction

    @contextlib.contextmanager
    def stalled_commit():
        with original_transaction():
            yield
        clock[0] = recorded + timedelta(seconds=31)

    monkeypatch.setattr(ledger, "transaction", stalled_commit)
    with pytest.raises(StateError, match="pre-observation timing"):
        ledger.begin_attempt(
            ledger.samples(run)[0]["id"], request, pre_observation_id=pre["observation_id"]
        )
    assert ledger.db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1
    assert ledger.db.execute("SELECT count(*) FROM deliveries").fetchone()[0] == 0
    assert ledger.attempt_observation_status(run)["status"] == "timing_violation"
    assert ledger.db.execute("SELECT count(*) FROM attempt_dispatch_aborts").fetchone()[0] == 1
    assert ledger.summary(run)["complete"] is False
    assert ledger.verify()["integrity"] == "verified"


def test_backwards_clock_during_delivery_blocks_a_matching_post(
    ledger, protocol, task, monkeypatch
):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, run, transport)
        sample = ledger.samples(run)[0]["id"]
        attempt = ledger.begin_attempt(sample, request, pre_observation_id=pre["observation_id"])
        started = datetime.fromisoformat(
            ledger.db.execute("SELECT started_at FROM attempts WHERE id=?", (attempt,)).fetchone()[
                0
            ]
        )
        clock = [started - timedelta(seconds=10)]
        monkeypatch.setattr(ledger_module, "now", lambda: clock[0].isoformat())
        token = ledger.finish_attempt(
            attempt,
            "returned",
            {},
            200,
            Generation(
                text="answer",
                returned_model="test-model",
                response_id=None,
                finish_reason="stop",
                usage={},
            ),
        )
        clock[0] = started - timedelta(seconds=9)
        observe_run(ledger, run, transport, attempt_id=attempt, post_token=token)
    timing = ledger.attempt_observation_status(run)
    assert timing["status"] == "timing_violation"
    assert timing["timing_violations"][0]["phase"] == "delivery"
    assert "model_observation_timing_violation" in ledger.summary(run)["score_blockers"]
    assert ledger.verify()["integrity"] == "verified"


def test_slow_delivery_persistence_counts_towards_post_delay(ledger, protocol, task, monkeypatch):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, run, transport)
        attempt = ledger.begin_attempt(
            ledger.samples(run)[0]["id"], request, pre_observation_id=pre["observation_id"]
        )
        started = datetime.fromisoformat(
            ledger.db.execute("SELECT started_at FROM attempts WHERE id=?", (attempt,)).fetchone()[
                0
            ]
        )
        clock = [started + timedelta(seconds=1)]
        monkeypatch.setattr(ledger_module, "now", lambda: clock[0].isoformat())
        original_blob = ledger._blob

        def slow_blob(value):
            if value == {"stall": True}:
                clock[0] = started + timedelta(seconds=130)
            return original_blob(value)

        monkeypatch.setattr(ledger, "_blob", slow_blob)
        token = ledger.finish_attempt(
            attempt,
            "returned",
            {"stall": True},
            200,
            Generation(
                text="answer",
                returned_model="test-model",
                response_id=None,
                finish_reason="stop",
                usage={},
            ),
        )
        clock[0] = started + timedelta(seconds=131)
        observe_run(ledger, run, transport, attempt_id=attempt, post_token=token)
    assert ledger.attempt_observation_status(run)["status"] == "timing_violation"
    assert ledger.attempt_observation_status(run)["timing_violations"][0]["phase"] == "post"


@pytest.mark.parametrize("checked_offset,phase", [(121, "post_commit"), (1, "post_confirmation")])
def test_slow_post_commit_cannot_make_late_durability_look_timely(
    ledger, protocol, task, monkeypatch, checked_offset, phase
):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, run, transport)
        attempt = ledger.begin_attempt(
            ledger.samples(run)[0]["id"], request, pre_observation_id=pre["observation_id"]
        )
        token = ledger.finish_attempt(attempt, "rejected", {}, 429)
        finished = datetime.fromisoformat(
            ledger.db.execute(
                "SELECT finished_at FROM deliveries WHERE attempt_id=?", (attempt,)
            ).fetchone()[0]
        )
        clock = [finished + timedelta(seconds=119)]
        monkeypatch.setattr(ledger_module, "now", lambda: clock[0].isoformat())
        original_transaction = ledger.transaction

        @contextlib.contextmanager
        def stalled_commit():
            with original_transaction():
                yield
            clock[0] = finished + timedelta(seconds=checked_offset)

        monkeypatch.setattr(ledger, "transaction", stalled_commit)
        observe_run(ledger, run, transport, attempt_id=attempt, post_token=token)
    timing = ledger.attempt_observation_status(run)
    assert timing["status"] == "timing_violation"
    assert timing["timing_violations"][0]["phase"] == phase
    assert ledger.verify()["integrity"] == "verified"


def test_crash_before_post_commit_check_keeps_run_unscored(ledger, protocol, task, monkeypatch):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, run, transport)
        sample = ledger.samples(run)[0]["id"]
        attempt = ledger.begin_attempt(sample, request, pre_observation_id=pre["observation_id"])
        token = ledger.finish_attempt(attempt, "rejected", {}, 429)
        original_transaction = ledger.transaction
        transactions = 0

        @contextlib.contextmanager
        def crash_before_check():
            nonlocal transactions
            transactions += 1
            if transactions == 2:
                raise RuntimeError("simulated process crash")
            with original_transaction():
                yield

        monkeypatch.setattr(ledger, "transaction", crash_before_check)
        with pytest.raises(RuntimeError, match="simulated process crash"):
            observe_run(ledger, run, transport, attempt_id=attempt, post_token=token)
    assert ledger.attempt_observation_status(run)["status"] == "missing_post_check"
    assert "model_post_observation_check_missing" in ledger.summary(run)["score_blockers"]
    with pytest.raises(StateError, match="complete model observations"):
        ledger.judge(sample, protocol.judge_digest, "pass", {})
    assert ledger.verify()["integrity"] == "verified"


def test_retry_gets_a_new_timed_observation_pair(ledger, protocol, task):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    sample = ledger.samples(run)[0]["id"]
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        transport = Transport(protocol.model, client=client)
        first_pre = observe_run(ledger, run, transport)
        first = ledger.begin_attempt(
            sample, request, pre_observation_id=first_pre["observation_id"]
        )
        first_token = ledger.finish_attempt(first, "rejected", {}, 429)
        observe_run(ledger, run, transport, attempt_id=first, post_token=first_token)
        second_pre = observe_run(ledger, run, transport)
        second = ledger.begin_attempt(
            sample, request, pre_observation_id=second_pre["observation_id"]
        )
        second_token = ledger.finish_attempt(
            second,
            "returned",
            {},
            200,
            Generation(
                text="answer",
                returned_model="test-model",
                response_id=None,
                finish_reason="stop",
                usage={},
            ),
        )
        observe_run(ledger, run, transport, attempt_id=second, post_token=second_token)
    assert ledger.attempt_observation_status(run)["status"] == "complete"
    assert ledger.db.execute("SELECT count(*) FROM post_observation_checks").fetchone()[0] == 2
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.parametrize("offset", [121, -1])
def test_late_or_backwards_post_observation_remains_bound_but_unscored(
    ledger, protocol, task, monkeypatch, offset
):
    protocol = _version(protocol)
    run = ledger.create_run(protocol)
    request = Ollama().prepare(protocol.model, task, None)
    with httpx.Client(transport=httpx.MockTransport(_metadata)) as client:
        transport = Transport(protocol.model, client=client)
        pre = observe_run(ledger, run, transport)
        sample = ledger.samples(run)[0]["id"]
        attempt = ledger.begin_attempt(sample, request, pre_observation_id=pre["observation_id"])
        token = ledger.finish_attempt(
            attempt,
            "returned",
            {"fixture": "returned before post metadata"},
            200,
            Generation(
                text="answer",
                returned_model="test-model",
                response_id=None,
                finish_reason="stop",
                usage={},
            ),
        )
        finished = ledger.db.execute(
            "SELECT finished_at FROM deliveries WHERE attempt_id=?", (attempt,)
        ).fetchone()[0]
        shifted = datetime.fromisoformat(finished) + timedelta(seconds=offset)
        monkeypatch.setattr(ledger_module, "now", lambda: shifted.isoformat())
        assert (
            observe_run(ledger, run, transport, attempt_id=attempt, post_token=token)["status"]
            == "stable_observed"
        )
        runner = GenerationRunner(ledger, run, {protocol.task_keys[0]: request}, transport)
        assert runner.step() == {
            "state": "stopped",
            "reason": "model_observation_timing_violation",
        }
    timing = ledger.attempt_observation_status(run)
    assert timing["status"] == "timing_violation"
    assert timing["timing_violations"][0]["phase"] == "post"
    assert "model_observation_timing_violation" in ledger.summary(run)["score_blockers"]
    assert ledger.db.execute("SELECT count(*) FROM generations").fetchone()[0] == 1
    with pytest.raises(StateError, match="model observations"):
        ledger.judge(sample, protocol.judge_digest, "pass", {})
    assert ledger.verify()["integrity"] == "verified"

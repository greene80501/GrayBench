import os
import sqlite3

import httpx
import pytest

from graybench.contracts import Generation
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import JudgmentRunner, UpstreamCampaign, cohort_identities
from graybench.judge import Judgment
from graybench.ledger import StateError
from graybench.provenance import source_manifest
from graybench.providers import Ollama
from graybench.transport import Transport
from graybench.upstream import UpstreamJudge

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "0" * 64)
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")


def configured(protocol, task):
    task = JudgeTask(
        public=task,
        canonical_solution="private reference",
        upstream_test="def check(candidate):\n    assert candidate(3)==4",
        upstream_difficulty="fixture",
    )
    judge = UpstreamJudge(image=IMAGE, docker=DOCKER)
    binding = cohort_identities((task,), judge)
    protocol = protocol.model_copy(
        update={
            "track": "upstream",
            "generation_code_digest": source_manifest()["digest"],
            **{k: binding[k] for k in ("dataset_digest", "judge_digest", "runtime_digest")},
        }
    )
    return protocol, task, judge


def saved_answer(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(protocol.model, task.public, None))
    ledger.finish_attempt(
        attempt,
        "returned",
        {},
        200,
        Generation(
            text="def answer(x): return x+1",
            returned_model="test-model",
            response_id=None,
            finish_reason="stop",
            usage={},
        ),
    )
    return run


def test_interrupted_judgment_is_not_rerolled(ledger, protocol, task, monkeypatch):
    protocol, task, judge = configured(protocol, task)
    run = saved_answer(ledger, protocol, task)
    calls = []

    def interrupted(*args):
        calls.append(args)
        raise KeyboardInterrupt()

    monkeypatch.setattr(judge, "evaluate", interrupted)
    runner = JudgmentRunner(ledger, run, (task,), judge)
    with pytest.raises(KeyboardInterrupt):
        runner.step()
    assert runner.step() == {"state": "stopped", "reason": "unresolved_judgment"}
    assert len(calls) == 1
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger.db.execute("DELETE FROM judgment_claims")
    assert ledger.summary(run)["pass_at_1"] is None


def test_changed_judge_identity_cannot_record_a_pass(ledger, protocol, task, monkeypatch):
    protocol, task, judge = configured(protocol, task)
    run = saved_answer(ledger, protocol, task)
    monkeypatch.setattr(judge, "evaluate", lambda *_: Judgment("pass", "0" * 64, {}))
    result = JudgmentRunner(ledger, run, (task,), judge).step()
    assert result["outcome"] == "infrastructure_error"
    assert ledger.summary(run)["pass_at_1"] is None


@pytest.mark.parametrize("change", ["dataset", "runtime", "request"])
def test_cohort_drift_prevents_network_or_judging(ledger, protocol, task, change):
    protocol, task, judge = configured(protocol, task)
    if change == "dataset":
        task = task.model_copy(update={"upstream_test": "def check(candidate): pass"})
    elif change == "runtime":
        judge = UpstreamJudge(image="sha256:" + "f" * 64)
    else:
        protocol = protocol.model_copy(
            update={"request_digests": {protocol.task_keys[0]: "0" * 64}}
        )
    run = ledger.create_run(protocol)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("network must not run"))
    ) as client:
        with pytest.raises(StateError):
            UpstreamCampaign(ledger, run, (task,), judge, Transport(protocol.model, client=client))
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Set immutable Docker image")
def test_saved_generations_flow_through_protected_judge_without_replacement(ledger, protocol, task):
    protocol, task, judge = configured(protocol, task)
    protocol = protocol.model_copy(update={"repeats": 2})
    calls = []

    def handler(request):
        calls.append(request)
        code = "def answer(x): return x+1" if len(calls) == 1 else "def answer(x): return 0"
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "done": True,
                "message": {"role": "assistant", "content": code},
            },
        )

    run = ledger.create_run(protocol)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        campaign = UpstreamCampaign(
            ledger, run, (task,), judge, Transport(protocol.model, client=client)
        )
        assert campaign.step()["state"] == "dispatched"
        assert campaign.step()["outcome"] == "pass"
        assert campaign.step()["state"] == "dispatched"
        assert campaign.step()["outcome"] == "fail"
        assert campaign.step()["state"] == "judgments_complete"
        assert campaign.step()["state"] == "judgments_complete"
    assert len(calls) == 2
    assert ledger.summary(run)["pass_at_1"] == 0.5
    assert ledger.summary(run)["certification"] == "not_certified"
    assert ledger.verify()["integrity"] == "verified"

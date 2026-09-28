import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from graybench.contracts import Generation, ModelSpec
from graybench.ledger import Ledger, StateError
from graybench.providers import Ollama


def returned(text=""):
    return Generation(
        text=text, returned_model="test-model", response_id=None, finish_reason="stop", usage={}
    )


def test_new_run_rejects_credentialed_model_without_public_scope(ledger, protocol):
    model = ModelSpec(
        adapter="openai-chat",
        model="test-model",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
    )
    edited = protocol.model_copy(update={"model": model})
    with pytest.raises(ValueError, match="credential_scope_id"):
        ledger.create_run(edited)


def test_new_run_rejects_copied_scope_containing_loaded_key(ledger, protocol, monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "unit-secret-456")
    model = ModelSpec(
        adapter="openai-chat",
        model="test-model",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
    ).model_copy(update={"credential_scope_id": "openai/project/unit-secret-456"})
    edited = protocol.model_copy(update={"model": model})
    with pytest.raises(ValueError, match="credential_scope_id"):
        ledger.create_run(edited)


def test_empty_return_cannot_be_retried(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    ledger.finish_attempt(attempt, "returned", {}, 200, returned())
    with pytest.raises(StateError, match="cannot be replaced"):
        ledger.begin_attempt(sample, request)
    assert ledger.summary(run)["pass_at_1"] is None
    ledger.judge(sample, protocol.judge_digest, "fail", {"reason": "empty answer"})
    assert ledger.summary(run)["pass_at_1"] == 0
    assert ledger.verify()["events"] == 4


def test_recovery_only_retries_explicit_transient_failure(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    first = ledger.begin_attempt(sample, request)
    with pytest.raises(StateError, match="not eligible"):
        ledger.begin_attempt(sample, request)
    ledger.finish_attempt(first, "rejected", {}, 503)
    second = ledger.begin_attempt(sample, request)
    ledger.finish_attempt(second, "ambiguous", {"reason": "read timeout"})
    with pytest.raises(StateError, match="not eligible"):
        ledger.begin_attempt(sample, request)


def test_retry_cannot_change_prompt(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    ledger.finish_attempt(attempt, "rejected", {}, 429)
    different = Ollama().prepare(protocol.model, task, "Here is the solution")
    with pytest.raises(StateError, match="identical"):
        ledger.begin_attempt(sample, different)


@pytest.mark.parametrize(
    "table",
    ["blobs", "runs", "samples", "attempts", "deliveries", "generations", "judgments", "events"],
)
def test_database_rejects_mutation(ledger, protocol, task, table):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(protocol.model, task, None))
    ledger.finish_attempt(attempt, "returned", {}, 200, returned())
    ledger.judge(sample, protocol.judge_digest, "fail", {})
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        ledger.db.execute(f"DELETE FROM {table}")


def test_unsupported_judgment_is_not_model_failure(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(protocol.model, task, None))
    ledger.finish_attempt(attempt, "returned", {}, 200, returned("pass"))
    ledger.judge(sample, protocol.judge_digest, "unsupported", {"type": "pending codec"})
    assert ledger.summary(run)["complete"] is False
    assert ledger.summary(run)["pass_at_1"] is None


def test_concurrent_dispatch_claim_has_one_winner(tmp_path, protocol, task):
    path = tmp_path / "shared.sqlite"
    ledger = Ledger(path)
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    ledger.close()
    request = Ollama().prepare(protocol.model, task, None)

    def claim(_):
        store = Ledger(path)
        try:
            store.begin_attempt(sample, request)
            return True
        except StateError:
            return False
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(claim, range(2))) == 1


def test_frozen_judge_controls_score(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(protocol.model, task, None))
    ledger.finish_attempt(attempt, "returned", {}, 200, returned())
    ledger.judge(sample, "a" * 64, "pass", {})
    assert ledger.summary(run)["pass_at_1"] is None


def test_retry_budget_is_enforced(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    for _ in range(protocol.retry.max_attempts):
        attempt = ledger.begin_attempt(sample, request)
        ledger.finish_attempt(attempt, "rejected", {}, 503)
    with pytest.raises(StateError, match="exhausted"):
        ledger.begin_attempt(sample, request)

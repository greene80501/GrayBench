import httpx
import pytest

from graybench.adapter_provenance import adapter_code_manifest
from graybench.campaign import GenerationRunner
from graybench.contracts import RetryPolicy
from graybench.ledger import Ledger, StateError
from graybench.provenance import source_manifest
from graybench.providers import Ollama
from graybench.transport import Transport


def setup(ledger, protocol, task, handler):
    protocol = protocol.model_copy(update={"generation_code_digest": source_manifest()["digest"]})
    run = ledger.create_run(protocol)
    requests = {protocol.task_keys[0]: Ollama().prepare(protocol.model, task, None)}
    discovery = {
        "/api/version": {"version": "fixture"},
        "/api/tags": {"models": [{"name": "test-model", "digest": "a" * 64}]},
        "/api/show": {"model_info": {"architecture": "fixture"}},
        "/api/ps": {"models": []},
    }

    def routed(request):
        if request.url.path in discovery:
            return httpx.Response(200, json=discovery[request.url.path])
        return handler(request)

    transport = Transport(
        protocol.model, client=httpx.Client(transport=httpx.MockTransport(routed))
    )
    return GenerationRunner(ledger, run, requests, transport)


def test_restart_respects_persisted_backoff_and_never_replaces_answer(
    tmp_path, protocol, task, monkeypatch
):
    import graybench.ledger as ledger_module

    timestamp = ["2026-01-01T00:00:00+00:00"]
    monkeypatch.setattr(ledger_module, "now", lambda: timestamp[0])
    protocol = protocol.model_copy(update={"retry": RetryPolicy(delays_seconds=(2.0, 10.0))})
    calls = []

    def handler(request):
        calls.append(request.content)
        return (
            httpx.Response(429)
            if len(calls) == 1
            else httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {"role": "assistant", "content": "def answer(x): return x+1"},
                    "done": True,
                },
            )
        )

    path = tmp_path / "resume.sqlite"
    ledger = Ledger(path)
    runner = setup(ledger, protocol, task, handler)
    assert runner.step()["delivery"] == "rejected"
    run_id, requests, transport = runner.run_id, runner.requests, runner.transport
    ledger.close()
    ledger = Ledger(path)
    try:
        runner = GenerationRunner(ledger, run_id, requests, transport)
        assert runner.step()["state"] == "deferred"
        sample = ledger.samples(run_id)[0]["id"]
        with pytest.raises(StateError, match="backoff"):
            ledger.begin_attempt(sample, next(iter(requests.values())))
        timestamp[0] = "2026-01-01T00:00:02+00:00"
        assert runner.step()["delivery"] == "returned"
        assert runner.step()["state"] == "generation_complete"
        assert calls[0] == calls[1]
        assert len(calls) == 2
        assert ledger.summary(run_id)["pass_at_1"] is None
    finally:
        ledger.close()
        transport.client.close()


@pytest.mark.parametrize("crash", [False, True])
def test_uncertain_delivery_stops_without_automatic_replay(ledger, protocol, task, crash):
    calls = []

    def handler(request):
        calls.append(request)
        if crash:
            raise KeyboardInterrupt()
        raise httpx.ReadTimeout("possibly generated")

    runner = setup(ledger, protocol, task, handler)
    if crash:
        with pytest.raises(KeyboardInterrupt):
            runner.step()
    else:
        assert runner.step()["delivery"] == "ambiguous"
    assert runner.step() == {"state": "stopped", "reason": "unresolved_delivery"}
    assert len(calls) == 1
    runner.transport.client.close()


def test_source_drift_prevents_any_network_call(ledger, protocol, task, monkeypatch):
    runner = setup(ledger, protocol, task, lambda _: pytest.fail("network must not run"))
    monkeypatch.setattr("graybench.campaign.source_manifest", lambda: {"digest": "0" * 64})
    with pytest.raises(StateError, match="source"):
        runner.step()
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    runner.transport.client.close()


def test_adapter_code_drift_prevents_model_observation_and_dispatch(ledger, protocol, task):
    forged = {**adapter_code_manifest(Ollama()), "engine_source_digest": "0" * 64}
    protocol = protocol.model_copy(update={"adapter_code_manifest": forged})
    runner = setup(ledger, protocol, task, lambda _: pytest.fail("network must not run"))
    with pytest.raises(StateError, match="(?i)adapter code"):
        runner.step()
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    runner.transport.client.close()


@pytest.mark.parametrize("status", [200, 400])
def test_empty_answer_and_permanent_rejection_are_never_retried(ledger, protocol, task, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            json={
                "model": "test-model",
                "done": True,
                "message": {"role": "assistant", "content": ""},
            },
        )

    runner = setup(ledger, protocol, task, handler)
    runner.step()
    assert runner.step()["state"] == ("generation_complete" if status == 200 else "stopped")
    assert len(calls) == 1
    runner.transport.client.close()

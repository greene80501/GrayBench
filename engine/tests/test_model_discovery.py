import httpx
import pytest

from graybench.campaign import GenerationRunner
from graybench.contracts import Observation
from graybench.model_discovery import discovery_identity, observe_run
from graybench.provenance import source_manifest
from graybench.providers import Ollama
from graybench.transport import Transport


def observations(digest="a" * 64, modified="today", loaded=True):
    return [
        Observation(name=name, status="observed", value=value)
        for name, value in {
            "/api/version": {"version": "fixture"},
            "/api/tags": {"models": [{"name": "test-model", "digest": digest}]},
            "/api/show": {
                "model_info": {"architecture": "fixture"},
                "template": "template",
                "modified_at": modified,
            },
            "/api/ps": {"models": ["volatile"] if loaded else []},
        }.items()
    ]


def test_volatile_load_state_does_not_change_model_identity(model):
    first = discovery_identity(model, observations())
    second = discovery_identity(model, observations(modified="tomorrow", loaded=False))
    assert first == second
    assert first["digest"] != discovery_identity(model, observations(digest="b" * 64))["digest"]


@pytest.mark.parametrize("digest", ["", "invalid"])
def test_invalid_model_digest_is_not_identity_evidence(model, digest):
    assert discovery_identity(model, observations(digest=digest))["status"] == "unavailable"


def test_digest_drift_blocks_generation_and_persists_evidence(ledger, protocol, task):
    protocol = protocol.model_copy(update={"generation_code_digest": source_manifest()["digest"]})
    run = ledger.create_run(protocol)
    responses = {o.name: o.value for o in observations()}
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.url.path != "/api/chat"
        return httpx.Response(200, json=responses[request.url.path])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = Transport(protocol.model, client=client)
        assert observe_run(ledger, run, transport)["status"] == "stable_observed"
        responses["/api/tags"] = observations(digest="b" * 64)[1].value
        runner = GenerationRunner(
            ledger,
            run,
            {protocol.task_keys[0]: Ollama().prepare(protocol.model, task, None)},
            transport,
        )
        assert runner.step() == {"state": "stopped", "reason": "model_discovery_unresolved"}
    assert ledger.discovery_status(run)["observations"] == 2
    assert ledger.summary(run)["pass_at_1"] is None
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    assert ledger.verify()["integrity"] == "verified"


def test_first_dispatch_observes_identity_before_generation(ledger, protocol, task):
    protocol = protocol.model_copy(update={"generation_code_digest": source_manifest()["digest"]})
    run = ledger.create_run(protocol)
    responses = {o.name: o.value for o in observations()}
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={
                    "model": "test-model",
                    "message": {"role": "assistant", "content": "def answer(x): return x + 1"},
                    "done": True,
                },
            )
        return httpx.Response(200, json=responses[request.url.path])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runner = GenerationRunner(
            ledger,
            run,
            {protocol.task_keys[0]: Ollama().prepare(protocol.model, task, None)},
            Transport(protocol.model, client=client),
        )
        assert runner.step()["delivery"] == "returned"
    assert calls == ["/api/version", "/api/tags", "/api/show", "/api/ps", "/api/chat"]
    assert ledger.discovery_status(run)["status"] == "stable_observed"
    assert ledger.discovery_status(run)["observations"] == 1
    assert ledger.verify()["integrity"] == "verified"


def test_first_dispatch_stops_if_discovery_unavailable(ledger, protocol, task):
    protocol = protocol.model_copy(update={"generation_code_digest": source_manifest()["digest"]})
    run = ledger.create_run(protocol)
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.url.path != "/api/chat"
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runner = GenerationRunner(
            ledger,
            run,
            {protocol.task_keys[0]: Ollama().prepare(protocol.model, task, None)},
            Transport(protocol.model, client=client),
        )
        assert runner.step() == {"state": "stopped", "reason": "model_discovery_unresolved"}
    assert calls == ["/api/version", "/api/tags", "/api/show", "/api/ps"]
    assert ledger.discovery_status(run)["status"] == "unresolved"
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    assert ledger.verify()["integrity"] == "verified"

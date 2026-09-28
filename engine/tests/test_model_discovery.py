import httpx
import pytest
from pydantic import ValidationError

from graybench.campaign import GenerationRunner
from graybench.contracts import Generation, ModelSpec, Observation
from graybench.model_discovery import discovery_identity, observe_run
from graybench.provenance import source_manifest
from graybench.providers import Adapter, Ollama, adapter
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


class NoMetadataAdapter(Adapter):
    name = "no-metadata-fixture"

    def prepare(self, spec, task, system):
        return self.request(spec, "/generate", {"model": spec.model, "prompt": task.prompt})

    def parse(self, response):
        return Generation(
            text=response["text"],
            returned_model=response["model"],
            response_id=None,
            finish_reason="complete",
            usage={},
        )


def test_no_metadata_adapter_stops_without_exception(ledger, protocol, task, monkeypatch):
    model = ModelSpec(
        adapter="no-metadata-fixture", model="test-model", base_url="https://provider.example"
    )
    provider = NoMetadataAdapter()
    monkeypatch.setattr("graybench.model_discovery.adapter", lambda _: provider)
    request = provider.prepare(model, task, None)
    protocol = protocol.model_copy(
        update={
            "model": model,
            "request_digests": {protocol.task_keys[0]: request.digest},
            "generation_code_digest": source_manifest()["digest"],
        }
    )
    run = ledger.create_run(protocol)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("generation must not run"))
    ) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(model, client=client)
        )
        assert runner.step() == {"state": "stopped", "reason": "model_discovery_unresolved"}
    assert ledger.discovery_status(run)["status"] == "unresolved"
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()


def test_no_metadata_adapter_requires_declared_development_exception(
    ledger, protocol, task, monkeypatch
):
    with pytest.raises(ValidationError, match="discovery_exception_reason"):
        ModelSpec(
            adapter="no-metadata-fixture",
            model="test-model",
            base_url="https://provider.example",
            discovery_policy="unverified_development",
        )
    model = ModelSpec(
        adapter="no-metadata-fixture",
        model="test-model",
        base_url="https://provider.example",
        discovery_policy="unverified_development",
        discovery_exception_reason="Provider exposes no model metadata endpoint",
    )
    provider = NoMetadataAdapter()
    monkeypatch.setattr("graybench.campaign.adapter", lambda _: provider)
    monkeypatch.setattr("graybench.model_discovery.adapter", lambda _: provider)
    request = provider.prepare(model, task, None)
    protocol = protocol.model_copy(
        update={
            "model": model,
            "request_digests": {protocol.task_keys[0]: request.digest},
            "generation_code_digest": source_manifest()["digest"],
        }
    )
    run = ledger.create_run(protocol)
    calls = []

    def handler(http_request):
        calls.append(http_request.url.path)
        return httpx.Response(200, json={"model": "test-model", "text": "answer"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(model, client=client)
        )
        assert runner.step()["delivery"] == "returned"
    assert calls == ["/generate"]
    status = ledger.discovery_status(run)
    assert status["status"] == "unverified_development"
    assert status["observations"] == 1
    sample_id = ledger.samples(run)[0]["id"]
    ledger.judge(sample_id, protocol.judge_digest, "pass", {})
    report = ledger.summary(run)
    assert report["pass_at_1"] == 1.0
    assert report["score_status"] == "development_only"
    assert report["publication_eligible"] is False
    assert "model_discovery_unverified" in report["publication_blockers"]
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.parametrize("declared_exception", [False, True])
def test_openai_compatible_chat_campaign_never_claims_verified_discovery(
    ledger, protocol, task, declared_exception
):
    model = ModelSpec(
        adapter="openai-compatible-chat",
        model="local-model",
        base_url="http://localhost:8000/v1",
        discovery_policy="unverified_development" if declared_exception else "required",
        discovery_exception_reason="No metadata route was calibrated"
        if declared_exception
        else None,
    )
    request = adapter(model.adapter).prepare(model, task, None)
    frozen = protocol.model_copy(
        update={
            "model": model,
            "request_digests": {protocol.task_keys[0]: request.digest},
            "generation_code_digest": source_manifest()["digest"],
        }
    )
    run = ledger.create_run(frozen)
    calls = []

    def handler(http_request):
        calls.append(http_request.url.path)
        assert http_request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": "local-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "def answer(x): return x + 1"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runner = GenerationRunner(
            ledger, run, {frozen.task_keys[0]: request}, Transport(model, client=client)
        )
        result = runner.step()
    if declared_exception:
        assert result["delivery"] == "returned"
        assert calls == ["/v1/chat/completions"]
        assert ledger.discovery_status(run)["status"] == "unverified_development"
        sample_id = ledger.samples(run)[0]["id"]
        ledger.judge(sample_id, frozen.judge_digest, "pass", {})
        report = ledger.summary(run)
        assert report["publication_eligible"] is False
        assert "model_discovery_unverified" in report["publication_blockers"]
    else:
        assert result == {"state": "stopped", "reason": "model_discovery_unresolved"}
        assert calls == []
        assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    assert ledger.verify()["integrity"] == "verified"


def test_declared_exception_cannot_bypass_available_discovery(ledger, protocol, task):
    model = protocol.model.model_copy(
        update={
            "discovery_policy": "unverified_development",
            "discovery_exception_reason": "Cannot inspect model",
        }
    )
    request = Ollama().prepare(model, task, None)
    protocol = protocol.model_copy(
        update={
            "model": model,
            "request_digests": {protocol.task_keys[0]: request.digest},
            "generation_code_digest": source_manifest()["digest"],
        }
    )
    run = ledger.create_run(protocol)
    calls = []

    def handler(http_request):
        calls.append(http_request.url.path)
        assert http_request.url.path != "/api/chat"
        return httpx.Response(503)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(model, client=client)
        )
        assert runner.step() == {"state": "stopped", "reason": "model_discovery_unresolved"}
    assert len(calls) == 4
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()

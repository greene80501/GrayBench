import httpx
import pytest

from graybench.campaign import GenerationRunner
from graybench.contracts import ModelSpec, Observation
from graybench.model_discovery import discovery_identity, observe_run
from graybench.provenance import source_manifest
from graybench.providers import adapter
from graybench.transport import Transport


def hosted_spec(name):
    return ModelSpec(adapter=name, model="test-model", base_url="https://provider.example/v1")


def metadata(name):
    if name == "gemini":
        return {
            "name": "models/test-model",
            "version": "001",
            "inputTokenLimit": 1000,
            "outputTokenLimit": 100,
            "supportedGenerationMethods": ["generateContent"],
            "thinking": True,
            "temperature": 1.0,
            "extra": {"future_field": "retained"},
        }
    return {
        "id": "test-model",
        "object": "model",
        "created": 1700000000,
        "owned_by": "fixture-provider",
        "extra": {"future_field": "retained"},
    }


@pytest.mark.parametrize("name", ["openai-chat", "openai-responses", "gemini"])
@pytest.mark.parametrize("change", ["metadata_drift", "unavailable"])
def test_hosted_baseline_blocks_dispatch_after_metadata_changes(
    ledger, protocol, task, name, change
):
    model = hosted_spec(name)
    request = adapter(name).prepare(model, task, None)
    protocol = protocol.model_copy(
        update={
            "model": model,
            "request_digests": {protocol.task_keys[0]: request.digest},
            "generation_code_digest": source_manifest()["digest"],
        }
    )
    run = ledger.create_run(protocol)
    body = metadata(name)
    status = 200

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/models/test-model"
        return httpx.Response(status, json=body, headers={"x-request-id": "catalog-fixture"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = Transport(model, client=client)
        assert observe_run(ledger, run, transport)["status"] == "stable_observed"
        if change == "metadata_drift":
            body["extra"]["future_field"] = "changed"
        else:
            status = 503
        runner = GenerationRunner(ledger, run, {protocol.task_keys[0]: request}, transport)
        assert runner.step() == {"state": "stopped", "reason": "model_discovery_unresolved"}
    assert not ledger.db.execute("SELECT 1 FROM attempts").fetchone()
    assert ledger.discovery_status(run)["observations"] == 2
    stored = [
        ledger.blob(row[0])
        for row in ledger.db.execute("SELECT content FROM model_observations ORDER BY id")
    ]
    first = stored[0]
    assert first["identity"]["identity"]["metadata"]["extra"] == {"future_field": "retained"}
    assert "not independent weight attestation" in first["identity"]["verification"]
    assert (
        first["observations"][0]["evidence"]["response_headers"]["x-request-id"]
        == "catalog-fixture"
    )
    assert stored[1]["observations"][0]["evidence"]["http_status"] == (
        503 if change == "unavailable" else 200
    )
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.parametrize("name", ["openai-chat", "openai-responses", "gemini"])
def test_hosted_metadata_rejects_other_models_and_duplicate_observations(name):
    model = hosted_spec(name)
    body = metadata(name)
    obs = Observation(name="/models/test-model", status="observed", value=body)
    assert discovery_identity(model, [obs])["status"] == "observed"
    assert discovery_identity(model, [obs, obs])["status"] == "unavailable"
    wrong = {**body, "name" if name == "gemini" else "id": "other-model"}
    assert (
        discovery_identity(model, [obs.model_copy(update={"value": wrong})])["status"]
        == "unavailable"
    )


def test_discovery_keeps_error_evidence_without_leaking_credentials(monkeypatch):
    monkeypatch.setenv("TEST_DISCOVERY_KEY", "fake-secret-for-test")
    model = hosted_spec("gemini").model_copy(update={"credential_env": "TEST_DISCOVERY_KEY"})

    def handler(request):
        assert request.headers["x-goog-api-key"] == "fake-secret-for-test"
        return httpx.Response(
            403, text='{"error":"fake-secret-for-test"}', headers={"x-request-id": "safe"}
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        observations = Transport(model, client=client).discover(adapter("gemini"))
    assert len(observations) == 1
    assert observations[0].status == "error"
    evidence = observations[0].model_dump()["evidence"]
    assert evidence["http_status"] == 403
    assert evidence["response_body"] == '{"error":"[REDACTED]"}'
    assert "fake-secret-for-test" not in observations[0].model_dump_json()


@pytest.mark.parametrize(
    "payload", ['{"id":"test-model","extra":NaN}', "[" * 1100 + "0" + "]" * 1100]
)
def test_malformed_discovery_is_recordable_error(payload):
    from graybench.identity import canonical

    model = hosted_spec("openai-chat")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=payload))
    ) as client:
        observations = Transport(model, client=client).discover(adapter(model.adapter))
    assert observations[0].status == "error"
    canonical(observations[0].model_dump(mode="json"))


def test_stable_hosted_baseline_allows_one_generation(ledger, protocol, task):
    model = hosted_spec("openai-chat")
    request = adapter(model.adapter).prepare(model, task, None)
    protocol = protocol.model_copy(
        update={
            "model": model,
            "request_digests": {protocol.task_keys[0]: request.digest},
            "generation_code_digest": source_manifest()["digest"],
        }
    )
    run = ledger.create_run(protocol)

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=metadata("openai-chat"))
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "def answer(x): return x + 1"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = Transport(model, client=client)
        assert observe_run(ledger, run, transport)["status"] == "stable_observed"
        runner = GenerationRunner(ledger, run, {protocol.task_keys[0]: request}, transport)
        assert runner.step()["delivery"] == "returned"
        assert runner.step()["state"] == "generation_complete"
    assert ledger.db.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1
    assert ledger.discovery_status(run)["observations"] == 2
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.parametrize("name", ["openai-chat", "openai-responses", "gemini"])
def test_first_hosted_dispatch_observes_before_generation(ledger, protocol, task, name):
    model = hosted_spec(name)
    request = adapter(name).prepare(model, task, None)
    protocol = protocol.model_copy(
        update={
            "model": model,
            "request_digests": {protocol.task_keys[0]: request.digest},
            "generation_code_digest": source_manifest()["digest"],
        }
    )
    run = ledger.create_run(protocol)
    calls = []
    generated = {
        "openai-chat": {
            "model": "test-model",
            "choices": [
                {"message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}
            ],
        },
        "openai-responses": {
            "model": "test-model",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "answer"}],
                }
            ],
        },
        "gemini": {
            "modelVersion": "test-model",
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"role": "model", "parts": [{"text": "answer"}]},
                }
            ],
        },
    }

    def handler(http_request):
        calls.append((http_request.method, http_request.url.path))
        return httpx.Response(
            200,
            json=metadata(name) if http_request.method == "GET" else generated[name],
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runner = GenerationRunner(
            ledger, run, {protocol.task_keys[0]: request}, Transport(model, client=client)
        )
        assert runner.step()["delivery"] == "returned"
    assert calls == [("GET", "/v1/models/test-model"), ("POST", "/v1" + request.path)]
    assert ledger.discovery_status(run)["status"] == "stable_observed"
    assert ledger.discovery_status(run)["observations"] == 1
    assert ledger.verify()["integrity"] == "verified"

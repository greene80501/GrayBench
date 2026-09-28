import gzip
import hashlib
import json
import zlib

import httpx
import pytest

from graybench.contracts import ModelSpec, Setting
from graybench.providers import (
    CapabilityError,
    Gemini,
    Ollama,
    OpenAIChat,
    OpenAIResponses,
    ResponseError,
    adapter,
)
from graybench.transport import Transport


@pytest.mark.parametrize("kind", [Ollama, OpenAIChat, OpenAIResponses, Gemini])
def test_adapters_never_add_test_reference_or_default_sampling(kind, task):
    model = ModelSpec(adapter=kind.name, model="test", base_url="https://example.test")
    request = kind().prepare(model, task, None)
    assert task.prompt in str(request.body)
    assert "temperature" not in str(request.body)
    assert "canonical_solution" not in str(request.body)
    assert "tools" not in request.body


@pytest.mark.parametrize("support", ["unknown", "ignored", "unsupported"])
def test_uncertain_settings_rejected_before_network(model, task, support):
    setting = Setting(name="temperature", value=0, support=support, evidence="unverified")
    model = ModelSpec(**{**model.model_dump(), "settings": (setting,)})
    with pytest.raises(CapabilityError):
        Ollama().prepare(model, task, None)


def test_openai_compatible_chat_requires_endpoint_verified_settings(task):
    provider = adapter("openai-compatible-chat")
    spec = ModelSpec(
        adapter=provider.name,
        model="local-model",
        base_url="http://localhost:8000/v1",
        settings=(
            Setting(name="temperature", value=0, support="documented", evidence="API shape only"),
        ),
    )
    with pytest.raises(CapabilityError, match="verified"):
        provider.prepare(spec, task, None)
    verified = spec.model_copy(
        update={
            "settings": (
                Setting(
                    name="temperature",
                    value=0,
                    support="verified",
                    evidence="Endpoint-specific conformance probe",
                ),
            )
        }
    )
    request = provider.prepare(verified, task, None)
    assert request.path == "/chat/completions"
    assert request.body["temperature"] == 0
    assert request.body["messages"] == [{"role": "user", "content": task.prompt}]
    assert provider.discovery_requests(verified) == ()


@pytest.mark.parametrize("name", ["openai-chat", "openai-compatible-chat"])
@pytest.mark.parametrize("role", [None, "user"])
def test_chat_response_requires_assistant_role(name, role):
    message = {"content": "def answer(x): return x + 1"}
    if role is not None:
        message["role"] = role
    with pytest.raises(ResponseError, match="assistant"):
        adapter(name).parse({"choices": [{"message": message, "finish_reason": "stop"}]})


def test_gemini_text_response_requires_model_role():
    with pytest.raises(ResponseError, match="model role"):
        Gemini().parse(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"role": "user", "parts": [{"text": "answer"}]},
                    }
                ]
            }
        )


def test_gemini_terminal_safety_block_without_content_consumes_answer():
    result = Gemini().parse(
        {
            "modelVersion": "gemini-fixture",
            "candidates": [
                {
                    "finishReason": "SAFETY",
                    "content": None,
                    "safetyRatings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT"}],
                }
            ],
        }
    )
    assert result.text == ""
    assert result.finish_reason == "SAFETY"
    assert result.metadata["safetyRatings"] == [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT"}]


def test_ollama_keeps_thinking_out_of_answer():
    generation = Ollama().parse(
        {
            "model": "test:latest",
            "done": True,
            "done_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "return 1",
                "thinking": "private reasoning",
            },
            "eval_count": 5,
        }
    )
    assert generation.text == "return 1"
    assert generation.metadata["thinking"] == "private reasoning"
    assert generation.usage["prompt_eval_count"] is None
    assert generation.effective_settings == {}


def test_transport_does_not_retry_timeout(model, task):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("unknown delivery")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = Transport(model, client=client)
        result = transport.generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "ambiguous"
    assert len(calls) == 1


def test_generation_authenticates_with_the_supplied_adapter_instance(monkeypatch, task):
    monkeypatch.setenv("TEST_TOKEN", "stateful-fixture-secret")
    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class StatefulOllama(Ollama):
        def __init__(self):
            self.auth_calls = 0

        def auth_headers(self, secret):
            self.auth_calls += 1
            return {"Authorization": f"Bearer {secret}"}

    provider = StatefulOllama()

    def handler(request):
        assert request.headers["Authorization"] == "Bearer stateful-fixture-secret"
        return httpx.Response(
            200,
            json={
                "model": model.model,
                "done": True,
                "message": {"role": "assistant", "content": "return 1"},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Transport(model, client).generate(provider.prepare(model, task, None), provider)
    assert result.kind == "returned"
    assert provider.auth_calls == 1
    assert "stateful-fixture-secret" not in str(result.evidence)


def test_discovery_authenticates_with_the_supplied_adapter_instance(monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "stateful-fixture-secret")
    model = ModelSpec(
        adapter="ollama",
        model="test-model",
        base_url="http://localhost:11434",
        credential_env="TEST_TOKEN",
    )

    class StatefulOllama(Ollama):
        def __init__(self):
            self.auth_calls = 0

        def auth_headers(self, secret):
            self.auth_calls += 1
            return {"Authorization": f"Bearer {secret}"}

    provider = StatefulOllama()

    def handler(request):
        assert request.headers["Authorization"] == "Bearer stateful-fixture-secret"
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        observations = Transport(model, client).discover(provider)
    assert len(observations) == 4
    assert all(observation.status == "observed" for observation in observations)
    assert provider.auth_calls == 4


def test_discovery_rejects_an_adapter_outside_the_frozen_model_identity(model):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"name": "models/test-model"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="adapter"):
            Transport(model, client).discover(Gemini())
    assert calls == []


def test_transport_sends_and_records_frozen_public_headers(model, task):
    class ProfiledOllama(Ollama):
        def public_headers(self, spec):
            return {"X-Model-Profile": "stable"}

    provider = ProfiledOllama()
    request = provider.prepare(model, task, None)

    def handler(wire_request):
        assert wire_request.headers["x-model-profile"] == "stable"
        assert wire_request.headers["accept-encoding"] == "identity"
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Transport(model, client).generate(request, provider)
    assert result.kind == "ambiguous"
    assert result.evidence["request_public_headers"] == request.public_headers
    assert (
        result.evidence["request_public_headers_sha256"]
        == hashlib.sha256(
            json.dumps(request.public_headers, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def test_changed_adapter_public_headers_stop_before_network(model, task):
    class ProfiledOllama(Ollama):
        def __init__(self):
            self.profile = "planned"

        def public_headers(self, spec):
            return {"X-Model-Profile": self.profile}

    provider = ProfiledOllama()
    request = provider.prepare(model, task, None)
    provider.profile = "changed"
    calls = []
    with httpx.Client(transport=httpx.MockTransport(lambda req: calls.append(req))) as client:
        with pytest.raises(ValueError, match="public headers"):
            Transport(model, client).generate(request, provider)
    assert calls == []


@pytest.mark.parametrize("auth_header", ["Accept", "X-Model-Profile", "X-Undeclared-Auth"])
def test_credential_headers_cannot_override_public_or_use_undeclared_names(
    model, task, auth_header
):
    class AuthOnly(Ollama):
        def public_headers(self, spec):
            return {"X-Model-Profile": "stable"}

        def auth_headers(self, secret):
            return {auth_header: "auth-value"}

    provider = AuthOnly()
    request = provider.prepare(model, task, None)
    calls = []
    with httpx.Client(transport=httpx.MockTransport(lambda req: calls.append(req))) as client:
        with pytest.raises(ValueError, match="credential header"):
            Transport(model, client).generate(request, provider)
    assert calls == []


def test_discovery_records_adapter_public_headers(model):
    class ProfiledOllama(Ollama):
        def public_headers(self, spec):
            return {"X-Model-Profile": "stable"}

    provider = ProfiledOllama()
    paths = []

    def handler(request):
        paths.append(request.url.path)
        assert request.headers["x-model-profile"] == "stable"
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        observations = Transport(model, client).discover(provider)
    assert len(paths) == 4
    assert all(
        o.evidence["request_public_headers"]["x-model-profile"] == "stable" for o in observations
    )


@pytest.mark.parametrize(
    "client_options",
    [
        {"headers": {"X-Hidden-Model-Mode": "altered"}},
        {"headers": {"Cookie": "session=hidden"}},
        {"params": {"model_mode": "altered"}},
    ],
)
def test_client_defaults_cannot_add_unfrozen_request_semantics(model, task, client_options):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": "unavailable"})

    provider = Ollama()
    with httpx.Client(transport=httpx.MockTransport(handler), **client_options) as client:
        with pytest.raises(ValueError, match="client.*(header|URL)"):
            Transport(model, client).generate(provider.prepare(model, task, None), provider)
    assert calls == []


def test_client_request_hook_cannot_mutate_headers_after_preflight(model, task):
    calls = []

    def hook(request):
        request.headers["X-Hidden-Model-Mode"] = "altered"

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": "unavailable"})

    provider = Ollama()
    with httpx.Client(
        transport=httpx.MockTransport(handler), event_hooks={"request": [hook]}
    ) as client:
        with pytest.raises(ValueError, match="client request hook"):
            Transport(model, client).generate(provider.prepare(model, task, None), provider)
    assert calls == []


def test_transport_redacts_echoed_key(monkeypatch, task):
    monkeypatch.setenv("TEST_TOKEN", "secret-for-unit-test")
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
    )

    def handler(request):
        assert request.headers["Authorization"] == "Bearer secret-for-unit-test"
        return httpx.Response(401, text='{"error":"secret-for-unit-test"}')

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Transport(model, client).generate(
            OpenAIChat().prepare(model, task, None), OpenAIChat()
        )
    assert result.kind == "rejected"
    assert "secret-for-unit-test" not in str(result.evidence)


def test_transport_records_exact_submitted_bytes_and_public_scope(monkeypatch, task):
    monkeypatch.setenv("TEST_TOKEN", "secret-for-unit-test")
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
        credential_scope_id="openai/project/graybench-evaluation",
    )
    request = OpenAIChat().prepare(model, task, None)
    submitted = []

    def handler(wire_request):
        submitted.append(wire_request.content)
        return httpx.Response(503, text='{"error":"overloaded"}')

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Transport(model, client).generate(request, OpenAIChat())
    assert len(submitted) == 1
    assert result.kind == "ambiguous"
    assert result.evidence["request_content_sha256"] == hashlib.sha256(submitted[0]).hexdigest()
    assert result.evidence["request_content_bytes"] == len(submitted[0])
    assert result.evidence["request_httpx_headers"]["content-length"] == str(len(submitted[0]))
    assert result.evidence["request_httpx_headers"]["host"] == "example.test"
    assert "authorization" not in result.evidence["request_httpx_headers"]
    assert result.evidence["credential_scope_id"] == "openai/project/graybench-evaluation"
    assert result.evidence["auth_header_names"] == ["authorization"]
    assert "secret-for-unit-test" not in str(result.evidence)


def test_transport_distinguishes_encoded_entity_from_decoded_response(model, task):
    decoded = json.dumps(
        {
            "model": model.model,
            "done": True,
            "message": {"role": "assistant", "content": "return 7"},
        }
    ).encode()
    encoded = gzip.compress(decoded)

    def handler(_request):
        assert _request.headers["Accept-Encoding"] == "identity"
        return httpx.Response(
            200,
            headers={"Content-Encoding": "gzip", "Content-Type": "application/json"},
            stream=httpx.ByteStream(encoded),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "returned"
    assert result.generation.text == "return 7"
    assert result.evidence["wire_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert result.evidence["wire_bytes"] == len(encoded)
    assert result.evidence["decoded_body_sha256"] == hashlib.sha256(decoded).hexdigest()
    assert result.evidence["response_bytes"] == len(decoded)
    assert result.evidence["response_headers"]["content-encoding"] == "gzip"
    assert result.evidence["response_capture_version"] == "encoded_entity_v2"


def test_auth_adapter_cannot_add_a_second_content_encoding_request_header(model, task):
    class AuthOnly(Ollama):
        def auth_headers(self, _secret):
            return {"accept-encoding": "gzip"}

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="credential header"):
            provider = AuthOnly()
            Transport(model, client).generate(provider.prepare(model, task, None), provider)
    assert calls == []


def test_transport_bounds_decoded_gzip_body_after_small_encoded_entity(model, task):
    decoded = json.dumps({"message": {"content": "x" * 4096}}).encode()
    encoded = gzip.compress(decoded)
    assert len(encoded) < 256 < len(decoded)

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                stream=httpx.ByteStream(encoded),
            )
        )
    ) as client:
        result = Transport(model, client, max_response_bytes=256).generate(
            Ollama().prepare(model, task, None), Ollama()
        )
    assert result.kind == "ambiguous"
    assert result.evidence["wire_bytes"] == len(encoded)
    assert result.evidence["wire_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert "decoded byte limit" in result.evidence["error"]


def test_preconsumed_gzip_response_does_not_claim_unavailable_wire_bytes(model, task):
    decoded = json.dumps(
        {
            "model": model.model,
            "done": True,
            "message": {"role": "assistant", "content": "return 8"},
        }
    ).encode()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                content=gzip.compress(decoded),
            )
        )
    ) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "returned"
    assert result.generation.text == "return 8"
    assert result.evidence["response_capture_version"] == "preconsumed_decoded_v1"
    assert result.evidence["wire_bytes"] is None
    assert "wire_sha256" not in result.evidence
    assert result.evidence["decoded_body_sha256"] == hashlib.sha256(decoded).hexdigest()


def test_malformed_compressed_response_is_ambiguous_with_encoded_digest(model, task):
    encoded = b"not-a-gzip-entity"
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                stream=httpx.ByteStream(encoded),
            )
        )
    ) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "ambiguous"
    assert result.evidence["error_type"] == "ValueError"
    assert result.evidence["wire_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert result.evidence["wire_bytes"] == len(encoded)
    assert result.evidence["response_bytes"] == 0


def test_truncated_gzip_trailer_cannot_be_a_returned_generation(model, task):
    decoded = json.dumps(
        {
            "model": model.model,
            "done": True,
            "message": {"role": "assistant", "content": "return 9"},
        }
    ).encode()
    encoded = gzip.compress(decoded)[:-8]
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                headers={"Content-Encoding": "gzip"},
                stream=httpx.ByteStream(encoded),
            )
        )
    ) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "ambiguous"
    assert result.generation is None
    assert result.evidence["wire_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert "incomplete" in result.evidence["error"]


def test_preconsumed_unbuffered_response_is_ambiguous_instead_of_raising(model, task):
    def handler(_request):
        response = httpx.Response(200, stream=httpx.ByteStream(b"{}"))
        assert b"".join(response.iter_raw()) == b"{}"
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "ambiguous"
    assert result.generation is None
    assert result.evidence["response_capture_version"] == "preconsumed_decoded_v1"
    assert result.evidence["wire_bytes"] is None
    assert "unavailable" in result.evidence["error"]


@pytest.mark.parametrize("raw_deflate", [False, True])
def test_transport_accepts_bounded_deflate_entity(model, task, raw_deflate):
    decoded = json.dumps(
        {
            "model": model.model,
            "done": True,
            "message": {"role": "assistant", "content": "return 10"},
        }
    ).encode()
    if raw_deflate:
        compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        encoded = compressor.compress(decoded) + compressor.flush()
    else:
        encoded = zlib.compress(decoded)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                headers={"Content-Encoding": "deflate"},
                stream=httpx.ByteStream(encoded),
            )
        )
    ) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "returned"
    assert result.generation.text == "return 10"
    assert result.evidence["wire_sha256"] == hashlib.sha256(encoded).hexdigest()


def test_unrequested_content_encoding_is_ambiguous(model, task):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                headers={"Content-Encoding": "br"},
                stream=httpx.ByteStream(b"opaque"),
            )
        )
    ) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "ambiguous"
    assert "Unsupported Content-Encoding" in result.evidence["error"]


def test_declared_account_scope_changes_frozen_model_identity():
    common = {
        "adapter": "openai-chat",
        "model": "test",
        "base_url": "https://example.test",
        "credential_env": "TEST_TOKEN",
    }
    first = ModelSpec(**common, credential_scope_id="openai/project/one")
    second = ModelSpec(**common, credential_scope_id="openai/project/two")
    assert first.digest != second.digest


@pytest.mark.parametrize("secret", ["sk-proj-fake", "AQ.fake-google-token"])
def test_api_key_shaped_scope_is_rejected_before_serialization(secret):
    with pytest.raises(ValueError, match="credential_scope_id"):
        ModelSpec(
            adapter="openai-chat",
            model="test",
            base_url="https://example.test",
            credential_env="TEST_TOKEN",
            credential_scope_id=secret,
        )


def test_actual_credential_cannot_hide_inside_public_scope(monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "unit-secret-456")
    with pytest.raises(ValueError, match="credential_scope_id"):
        ModelSpec(
            adapter="openai-chat",
            model="test",
            base_url="https://example.test",
            credential_env="TEST_TOKEN",
            credential_scope_id="openai/project/unit-secret-456",
        )


def test_transport_rejects_mismatched_prepared_model_before_network(model, task):
    request = Ollama().prepare(model, task, None)
    changed = request.model_copy(update={"model": "a-different-model"})
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("network must not be called"))
    ) as client:
        with pytest.raises(ValueError, match="prepared request"):
            Transport(model, client).generate(changed, Ollama())


def test_successful_response_echoing_credential_cannot_be_judged_as_changed_code(monkeypatch, task):
    secret = "secret-for-unit-test"
    monkeypatch.setenv("TEST_TOKEN", secret)
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
    )
    answer = f"def answer(): return {secret!r}"
    response = {
        "model": "test",
        "choices": [{"message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
    }
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response))
    ) as client:
        result = Transport(model, client).generate(
            OpenAIChat().prepare(model, task, None), OpenAIChat()
        )
    assert result.kind == "ambiguous"
    assert result.generation is None
    assert result.evidence["error_type"] == "CredentialEcho"
    assert secret not in str(result.evidence)
    assert "[REDACTED]" in result.evidence["response_body"]


def test_malformed_success_is_not_retried(model, task):
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="oops"))
    ) as client:
        result = Transport(model, client).generate(Ollama().prepare(model, task, None), Ollama())
    assert result.kind == "ambiguous"


def test_gemini_refusal_is_returned_answer():
    result = Gemini().parse({"promptFeedback": {"blockReason": "SAFETY"}})
    assert result.text == ""
    assert result.finish_reason == "prompt_blocked"


def test_responses_incomplete_preserves_answer_and_reason():
    result = OpenAIResponses().parse(
        {
            "status": "incomplete",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "def answer(x):"}],
                }
            ],
            "incomplete_details": {"reason": "max_output_tokens"},
        }
    )
    assert result.text == "def answer(x):"
    assert result.metadata["incomplete_details"]["reason"] == "max_output_tokens"

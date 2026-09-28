import hashlib

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
    assert result.evidence["credential_scope_id"] == "openai/project/graybench-evaluation"
    assert result.evidence["auth_header_names"] == ["authorization"]
    assert "secret-for-unit-test" not in str(result.evidence)


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

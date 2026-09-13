import httpx
import pytest

from graybench.contracts import ModelSpec, Setting
from graybench.providers import CapabilityError, Gemini, Ollama, OpenAIChat, OpenAIResponses
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

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import types
from openai.types.chat import ChatCompletion

from graybench.providers import GenerationRequest, TokenUsage
from graybench.providers.google_adapter import GoogleAdapter
from graybench.providers.openai_adapter import OpenAIAdapter
from graybench.execution import ExecutionHarness, Outcome
from test_evaluation import example


def test_google_uses_only_final_answer_and_accounts_for_reasoning():
    response = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    parts=[
                        types.Part(text="private reasoning", thought=True),
                        types.Part(text="def answer(x): return x + 1"),
                    ]
                ),
                finish_reason="STOP",
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10,
            candidates_token_count=20,
            thoughts_token_count=30,
            total_token_count=60,
        ),
    )
    generate = Mock(return_value=response)
    adapter = GoogleAdapter(
        api_key="fake", client=SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    )
    result = adapter.generate(GenerationRequest(prompt="public prompt", model="gemini-2.5-flash"))
    assert result.completion_text == "def answer(x): return x + 1"
    assert result.usage.output_tokens == 50 and result.usage.reasoning_tokens == 30
    config = generate.call_args.kwargs["config"]
    assert config.tools is None and config.automatic_function_calling.disable
    assert config.candidate_count == 1 and config.system_instruction is None
    assert generate.call_count == 1


def test_openai_records_actual_request_without_hidden_help():
    response = ChatCompletion.model_validate(
        {
            "id": "test",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "code"},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
    )
    create = Mock(return_value=response)
    adapter = OpenAIAdapter(
        api_key="fake",
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
    )
    result = adapter.generate(GenerationRequest(prompt="public prompt", model=response.model))
    params = create.call_args.kwargs
    assert params["messages"] == [{"role": "user", "content": "public prompt"}]
    assert "tools" not in params and "n" not in params
    assert result.raw_response["graybench_request"] == params
    assert create.call_count == 1


def test_google_price_tiers_and_unknown_variants():
    adapter = GoogleAdapter.__new__(GoogleAdapter)
    assert adapter.calculate_cost(
        TokenUsage(input_tokens=200001, output_tokens=1000000), "gemini-2.5-pro"
    ) == pytest.approx(15.5000025)
    assert adapter.calculate_cost(
        TokenUsage(input_tokens=1000000, cached_tokens=1000000), "gemini-2.5-flash"
    ) == pytest.approx(0.03)
    assert adapter.calculate_cost(TokenUsage(input_tokens=1), "gemini-2.5-flash-image") is None


def test_openai_unknown_suffix_is_not_assigned_another_model_price():
    adapter = OpenAIAdapter.__new__(OpenAIAdapter)
    assert adapter.calculate_cost(TokenUsage(input_tokens=1), "gpt-4o-made-up") is None
    assert adapter.calculate_cost(
        TokenUsage(input_tokens=1000000, cached_tokens=1000000), "gpt-4.1-mini-2025-04-14"
    ) == pytest.approx(0.1)


def test_excessive_output_is_stopped_and_not_scored_as_pass():
    result = ExecutionHarness(max_output_bytes=4096).execute(
        example(), "def answer(x):\n    print('x' * 1000000)\n    return x + 1"
    )
    assert not result.passed and result.outcome == Outcome.OUTPUT_LIMIT


def test_google_depleted_credits_are_not_transient_rate_limits():
    from graybench.providers import ProviderError, RateLimitError

    error = RuntimeError("Your prepayment credits are depleted")
    error.code = 429
    generate = Mock(side_effect=error)
    adapter = GoogleAdapter(
        api_key="fake", client=SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    )
    with pytest.raises(ProviderError, match="billing_or_quota_unavailable") as caught:
        adapter.generate(GenerationRequest(prompt="test", model="gemini-3.6-flash"))
    assert not isinstance(caught.value, RateLimitError)
    assert generate.call_count == 1

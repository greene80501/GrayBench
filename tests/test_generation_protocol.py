from types import SimpleNamespace

import pytest

from graybench.cli import _run_benchmark
from graybench.providers.base import GenerationRequest, GenerationResult, TokenUsage
from graybench.providers.openai_adapter import OpenAIAdapter
from test_evaluation import example


def test_empty_completion_is_one_attempt_and_its_usage_is_preserved():
    requests, records = [], []

    def generate(request):
        requests.append(request)
        return GenerationResult("fake", "model", request.prompt, "", TokenUsage(10, 20), 0.1, 1)

    _run_benchmark(
        SimpleNamespace(generate=generate),
        None,
        SimpleNamespace(record_attempt=lambda **row: records.append(row)),
        "run",
        "model",
        [example()],
        1,
        0,
        100,
    )
    assert len(requests) == len(records) == 1
    assert records[0]["output_tokens"] == 20
    assert records[0]["cost_usd"] == 0.1
    assert requests[0].prompt == example().prompt
    assert example().test not in requests[0].prompt
    assert example().canonical_solution not in requests[0].prompt


@pytest.mark.parametrize("extra", [{"n": 5}, {"tools": []}, {"messages": []}, {"model": "other"}])
def test_baseline_cannot_override_task_or_add_tools(extra):
    with pytest.raises(ValueError, match="Unsupported"):
        GenerationRequest("prompt", "model", extra_params=extra).validate_baseline(("seed",))


def test_pricing_selects_longest_model_prefix_and_unknown_is_not_guessed():
    adapter = OpenAIAdapter(api_key="not-a-real-key")
    assert adapter.calculate_cost(TokenUsage(1_000_000, 0), "gpt-4o-mini-2024-07-18") == 0.15
    assert adapter.calculate_cost(TokenUsage(1, 1), "unknown-model") is None

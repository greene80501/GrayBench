# Provider integration

Provider adapters implement `ProviderAdapter.generate(GenerationRequest)` and `calculate_cost(TokenUsage, model)` in `graybench/providers`. Register adapters in that package and provider configuration in `graybench/config.py`. The one shared price table is `graybench/pricing.py`; rates are estimates, and unknown models have no fallback price.

## OpenAI

The current adapter uses the official OpenAI SDK's Chat Completions endpoint. Exact snapshot IDs are accepted. GPT-4o mini was exercised live; o3 accepts `--reasoning-effort high` and uses `max_completion_tokens` without temperature/top-p overrides. Responses-only models require an additional endpoint implementation and must not be assumed supported merely because a model is listed. Cached and reasoning usage come from response details. SDK retries are disabled; only explicit transient rate limits are retried by the runner.

## Google

The adapter uses `google-genai`, requests one candidate, disables automatic function calling, and reads only non-thought text as the final answer. Output usage includes reported thought tokens. An empty/blocked/truncated response is retained. Model listing alone does not prove generation access: Gemini 2.5 Flash was listed but rejected for a newly configured account; Gemini 3.6 Flash then reported depleted prepayment credits. Billing/access failures are operational failures, not capability scores.

Google 2.5 text prices and the 3.6 Flash promotional text prices were checked against [Google's pricing page](https://ai.google.dev/gemini-api/docs/pricing) on 2026-09-13. The 3.6 rates change after 2026-12-31; revalidate prices before later runs. OpenAI pilot rates and o3 were checked against their [model documentation](https://developers.openai.com/api/docs/models/o3). Other inherited rate entries need revalidation before new paid runs.

## Other integrations

Anthropic, DeepSeek and Moonshot adapters remain in the project, but their accounts were not configured or exercised live during this audit. GrayGate is an agent-system track; its tests use a mocked service. It has no assumed zero price or fabricated token usage. Its unknown price prevents automatic paid runs until a real cost policy is provided.

Provider extra parameters are allowlisted for the baseline. They cannot override prompts, inject tools, request multiple candidates or replace model IDs. Full actual request parameters are retained beside raw responses. Never place API keys in result metadata, source control or candidate execution environments.

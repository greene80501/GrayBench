# Provider Integration Notes

This document contains technical details for each supported AI provider,
including API specifics, quirks, and integration notes.

## OpenAI

### Models

| Model ID | Description | Context | Notes |
|----------|-------------|---------|-------|
| gpt-5.2 | Flagship model | 400K | Best general performance |
| gpt-5.2-pro | High precision | 400K | More expensive, higher quality |
| gpt-5.2-codex | Code specialized | 400K | Optimized for code generation |
| gpt-4o | Previous flagship | 128K | Good baseline |
| gpt-4o-mini | Efficient | 128K | Cost-effective |
| o1 | Reasoning model | 200K | Chain-of-thought |
| o1-mini | Efficient reasoning | 128K | |
| o1-pro | Advanced reasoning | 200K | Premium |

### API Details

- **Endpoint**: `https://api.openai.com/v1/chat/completions`
- **Auth**: Bearer token (`OPENAI_API_KEY`)
- **SDK**: Official `openai` Python package

### Usage Fields

```python
response.usage.prompt_tokens
response.usage.completion_tokens
response.usage.total_tokens
response.usage.prompt_tokens_details.cached_tokens  # If applicable
```

### Quirks

- o1 models don't support temperature/top_p parameters
- Use `max_completion_tokens` instead of `max_tokens` for o1

### Pricing (as of Jan 2026)

| Model | Input $/M | Output $/M |
|-------|-----------|------------|
| gpt-5.2 | $1.75 | $14.00 |
| gpt-5.2-pro | $5.00 | $30.00 |
| gpt-5.2-codex | $2.50 | $10.00 |
| gpt-4o | $2.50 | $10.00 |
| gpt-4o-mini | $0.15 | $0.60 |

---

## Anthropic

### Models

| Model ID | Description | Context |
|----------|-------------|---------|
| claude-opus-4-5-20251101 | Most capable | 200K |
| claude-sonnet-4-5-20250929 | Best for coding | 200K |
| claude-haiku-4-5-20251001 | Fast & efficient | 200K |
| claude-4.5-opus-latest | Alias to latest opus | 200K |
| claude-4.5-sonnet-latest | Alias to latest sonnet | 200K |

### API Details

- **Endpoint**: `https://api.anthropic.com/v1/messages`
- **Auth**: `x-api-key` header (`ANTHROPIC_API_KEY`)
- **SDK**: Official `anthropic` Python package

### Usage Fields

```python
response.usage.input_tokens
response.usage.output_tokens
response.usage.cache_read_input_tokens  # If caching enabled
```

### Quirks

- Content returned as blocks, need to extract text
- Supports system prompts separately from user messages

### Pricing (as of Jan 2026)

| Model | Input $/M | Output $/M |
|-------|-----------|------------|
| claude-opus-4.5 | $5.00 | $25.00 |
| claude-sonnet-4.5 | $3.00 | $15.00 |
| claude-haiku-4.5 | $0.80 | $4.00 |

---

## Google (Gemini)

### Models

| Model ID | Description | Context |
|----------|-------------|---------|
| gemini-3-pro-preview | Most capable | 1M |
| gemini-3-flash-preview | Fast | 1M |
| gemini-2.0-flash | Previous gen | 1M |
| gemini-1.5-pro | Previous flagship | 2M |

### API Details

- **Endpoint**: Gemini API (Google AI Studio)
- **Auth**: API key (`GOOGLE_API_KEY`)
- **SDK**: `google-generativeai` package

### Usage Fields

```python
response.usage_metadata.prompt_token_count
response.usage_metadata.candidates_token_count
```

### Quirks

- Async API via `generate_content_async`
- Response structure differs from OpenAI
- May need to handle safety filters

### Pricing (as of Jan 2026)

| Model | Input $/M | Output $/M |
|-------|-----------|------------|
| gemini-3-pro | $1.25 | $5.00 |
| gemini-3-flash | $0.075 | $0.30 |

---

## DeepSeek

### Models

| Model ID | Description | Context |
|----------|-------------|---------|
| deepseek-chat | General purpose | 64K |
| deepseek-reasoner | With chain-of-thought | 64K |

### API Details

- **Endpoint**: `https://api.deepseek.com/v1` (OpenAI-compatible)
- **Auth**: Bearer token (`DEEPSEEK_API_KEY`)
- **SDK**: Can use `openai` package with custom base_url

### Quirks

- Fully OpenAI-compatible API
- Reasoner model may include reasoning traces
- Very cost-effective

### Pricing (as of Jan 2026)

| Model | Input $/M | Output $/M |
|-------|-----------|------------|
| deepseek-chat | $0.14 | $0.28 |
| deepseek-reasoner | $0.55 | $2.19 |

---

## Moonshot (Kimi)

### Models

| Model ID | Description | Context |
|----------|-------------|---------|
| kimi-k2.5 | Latest flagship | 256K |
| kimi-k2 | Previous version | 256K |
| kimi-k2-thinking | With reasoning | 256K |

### API Details

- **Endpoint**: `https://api.moonshot.ai/v1` (OpenAI-compatible)
- **Auth**: Bearer token (`MOONSHOT_API_KEY`)
- **SDK**: Can use `openai` package with custom base_url

### Quirks

- OpenAI-compatible API format
- Thinking models may output reasoning
- Large context window

### Pricing (as of Jan 2026)

| Model | Input $/M | Output $/M |
|-------|-----------|------------|
| kimi-k2.5 | $0.57 | $2.85 |
| kimi-k2 | $0.50 | $2.50 |
| kimi-k2-thinking | $0.60 | $3.00 |

---

## Adding New Providers

To add a new provider:

1. Create adapter in `graybench/adapters/new_provider_adapter.py`
2. Inherit from `BaseAdapter`
3. Implement required methods:
   - `is_configured()`
   - `list_models()`
   - `generate()`
4. Register in `graybench/adapters/__init__.py`
5. Add pricing to `graybench/config.py`
6. Document in this file

### Adapter Template

```python
class NewProviderAdapter(BaseAdapter):
    provider_name = "newprovider"
    
    def __init__(self):
        super().__init__()
        self._api_key = os.getenv("NEWPROVIDER_API_KEY")
    
    def is_configured(self) -> bool:
        return self._api_key is not None
    
    def list_models(self) -> List[str]:
        return ["model-a", "model-b"]
    
    async def generate(self, model, prompt, temperature, top_p, max_tokens, **kwargs):
        # Implementation
        pass
```

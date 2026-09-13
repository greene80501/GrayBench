"""
Anthropic provider adapter.

Supports Claude 3.5, Claude 4, and Claude 4.5 models.
"""

import os
from typing import Any, Dict, Optional

from anthropic import Anthropic, APIError, RateLimitError as AnthropicRateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from graybench.providers.base import (
    ProviderAdapter,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
    ProviderError,
    RateLimitError,
    AuthenticationError,
)

# Pricing per 1M tokens
from graybench.pricing import PRICING

ANTHROPIC_PRICING = PRICING["anthropic"]


class AnthropicAdapter(ProviderAdapter):
    """
    Anthropic API adapter.

    Supports the Messages API for all Claude models.
    """

    provider_name = "anthropic"

    supported_models = [
        "claude-opus-4-5-20251101",
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-1-20250805",
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
    ]

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        """
        Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            base_url: Optional custom base URL
        """
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)

        self.client = Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=kwargs.get("timeout", 120),
            max_retries=0,
        )

    @retry(
        retry=retry_if_exception_type(AnthropicRateLimitError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
    )
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a completion using Anthropic's API.

        Args:
            request: Generation request parameters

        Returns:
            GenerationResult with the completion
        """
        request.validate_baseline(("thinking",))
        start_time = self._time_request()

        # Build messages
        messages = [{"role": "user", "content": request.prompt}]

        # Build request parameters
        params: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        # Add system prompt if provided
        if request.system_prompt:
            params["system"] = request.system_prompt

        if request.stop_sequences:
            params["stop_sequences"] = request.stop_sequences

        # Add any extra parameters
        params.update(request.extra_params)

        try:
            response = self.client.messages.create(**params)

            latency_ms = self._calculate_latency_ms(start_time)

            # Extract completion text
            completion_text = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, "text"):
                        completion_text += block.text

            # Extract usage
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens if response.usage else 0,
                output_tokens=response.usage.output_tokens if response.usage else 0,
            )

            # Calculate cost
            cost_usd = self.calculate_cost(usage, request.model)

            # Convert response to dict for storage
            raw_response = {
                "graybench_request": params,
                "id": response.id,
                "type": response.type,
                "role": response.role,
                "model": response.model,
                "stop_reason": response.stop_reason,
                "stop_sequence": response.stop_sequence,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                },
            }

            return GenerationResult(
                provider=self.provider_name,
                model=request.model,
                prompt_text=request.prompt,
                completion_text=completion_text,
                usage=usage,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                raw_response=raw_response,
                request_id=response.id,
            )

        except AnthropicRateLimitError as e:
            raise RateLimitError(self.provider_name)
        except APIError as e:
            if "authentication" in str(e).lower() or "api_key" in str(e).lower():
                raise AuthenticationError(str(e), self.provider_name)
            raise ProviderError(str(e), self.provider_name, request.model)

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        """
        Calculate the cost in USD.

        Args:
            usage: Token usage information
            model: Model identifier

        Returns:
            Cost in USD
        """
        pricing = ANTHROPIC_PRICING.get(model)
        if not pricing:
            # Try to find a matching base model
            for base_model in ANTHROPIC_PRICING:
                if model.startswith(base_model.rsplit("-", 1)[0]):
                    pricing = ANTHROPIC_PRICING[base_model]
                    break

        if not pricing:
            # Default to Sonnet pricing if unknown
            return None

        input_cost = (usage.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

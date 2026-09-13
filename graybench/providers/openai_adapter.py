"""
OpenAI provider adapter.

Supports GPT-4, GPT-4o, o1, and future GPT-5.x models.
"""

import os
import re
from typing import Any, Dict, Optional

from openai import OpenAI, APIError, RateLimitError as OpenAIRateLimitError
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

OPENAI_PRICING = PRICING["openai"]


class OpenAIAdapter(ProviderAdapter):
    """
    OpenAI API adapter.

    Supports the Chat Completions API for all GPT models.
    """

    provider_name = "openai"

    supported_models = [
        "gpt-5.2",
        "gpt-5.2-pro",
        "gpt-5.1",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o3",
        "o3-pro",
        "o4-mini",
        "o1",
        "o1-mini",
        "o1-pro",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        organization: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the OpenAI adapter.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Optional custom base URL
            organization: Optional organization ID
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)

        self.client = kwargs.get("client") or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=kwargs.get("timeout", 120),
            max_retries=0,
            organization=organization,
        )

    @retry(
        retry=retry_if_exception_type(OpenAIRateLimitError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
    )
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a completion using OpenAI's API.

        Args:
            request: Generation request parameters

        Returns:
            GenerationResult with the completion
        """
        request.validate_baseline(("reasoning_effort", "seed", "verbosity"))
        start_time = self._time_request()

        # Build messages
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        # Build request parameters
        params: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }
        # Models that require max_completion_tokens
        if request.model.startswith("o") or request.model.startswith("gpt-5"):
            params["max_completion_tokens"] = request.max_tokens
        else:
            params["max_tokens"] = request.max_tokens

        # Models with fixed/default sampling params
        if not (request.model.startswith("o") or request.model.startswith("gpt-5")):
            params["temperature"] = request.temperature
            params["top_p"] = request.top_p

        if request.stop_sequences:
            params["stop"] = request.stop_sequences

        # Add any extra parameters
        extra_params = dict(request.extra_params) if request.extra_params else {}
        if request.model.startswith("o") or request.model.startswith("gpt-5"):
            # Ensure legacy max_tokens isn't sent for o-series models
            extra_params.pop("max_tokens", None)
        params.update(extra_params)
        if request.model.startswith("o") or request.model.startswith("gpt-5"):
            params.pop("max_tokens", None)

        try:
            response = self.client.chat.completions.create(**params)

            latency_ms = self._calculate_latency_ms(start_time)

            # Extract completion text
            completion_text = ""
            if response.choices and response.choices[0].message:
                completion_text = response.choices[0].message.content or ""

            # Extract usage
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )

            # Handle cached tokens if present
            completion_details = getattr(response.usage, "completion_tokens_details", None)
            usage.reasoning_tokens = getattr(completion_details, "reasoning_tokens", 0) or 0
            if (
                hasattr(response.usage, "prompt_tokens_details")
                and response.usage.prompt_tokens_details
            ):
                if hasattr(response.usage.prompt_tokens_details, "cached_tokens"):
                    usage.cached_tokens = response.usage.prompt_tokens_details.cached_tokens

            # Calculate cost
            cost_usd = (
                self.calculate_cost(usage, request.model) if response.usage is not None else None
            )

            return GenerationResult(
                provider=self.provider_name,
                model=request.model,
                prompt_text=request.prompt,
                completion_text=completion_text,
                usage=usage,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                raw_response={**response.model_dump(), "graybench_request": params},
                request_id=response.id,
            )

        except OpenAIRateLimitError as e:
            if "insufficient_quota" in str(e):
                raise ProviderError(
                    "insufficient_quota: OpenAI billing balance or quota must be updated",
                    self.provider_name,
                    request.model,
                ) from e
            raise RateLimitError(self.provider_name, retry_after=getattr(e, "retry_after", None))
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
        pricing = OPENAI_PRICING.get(model)
        if not pricing:
            # Try to find a matching base model
            for base_model in sorted(OPENAI_PRICING, key=len, reverse=True):
                if re.fullmatch(re.escape(base_model) + r"-\d{4}-\d{2}-\d{2}", model):
                    pricing = OPENAI_PRICING[base_model]
                    break

        if not pricing:
            return None

        input_cost = (usage.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output"]

        # Use the model's own cached-input rate.
        if usage.cached_tokens > 0:
            cached_cost = (usage.cached_tokens / 1_000_000) * pricing["cached"]
            regular_input = usage.input_tokens - usage.cached_tokens
            input_cost = (regular_input / 1_000_000) * pricing["input"] + cached_cost

        return input_cost + output_cost

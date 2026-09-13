"""
Moonshot (Kimi) provider adapter.

Moonshot AI provides an OpenAI-compatible API for Kimi models.
Supports Kimi K2 and K2.5 series.
"""

import os
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

# Moonshot API base URL
MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"

# Pricing per 1M tokens
from graybench.pricing import PRICING

MOONSHOT_PRICING = PRICING["moonshot"]


class MoonshotAdapter(ProviderAdapter):
    """
    Moonshot (Kimi) API adapter.

    Uses OpenAI-compatible API with custom base URL.
    """

    provider_name = "moonshot"

    supported_models = [
        "kimi-k2.5",
        "kimi-k2-thinking",
        "kimi-k2-turbo-preview",
    ]

    _FIXED_TEMPERATURE_MODELS = {
        "kimi-k2.5",
    }
    _FIXED_TOP_P_MODELS = {
        "kimi-k2.5": 0.95,
    }

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        """
        Initialize the Moonshot adapter.

        Args:
            api_key: Moonshot API key (defaults to MOONSHOT_API_KEY env var)
            base_url: Optional custom base URL
        """
        api_key = api_key or os.getenv("MOONSHOT_API_KEY")
        base_url = base_url or MOONSHOT_BASE_URL
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=kwargs.get("timeout", 120),
            max_retries=0,
        )

    @retry(
        retry=retry_if_exception_type(OpenAIRateLimitError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
    )
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a completion using Moonshot's API.

        Args:
            request: Generation request parameters

        Returns:
            GenerationResult with the completion
        """
        request.validate_baseline(("thinking",))
        start_time = self._time_request()

        # Build messages
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        # Build request parameters
        temperature = request.temperature
        if request.model in self._FIXED_TEMPERATURE_MODELS:
            temperature = 1.0
        top_p = request.top_p
        if request.model in self._FIXED_TOP_P_MODELS:
            top_p = self._FIXED_TOP_P_MODELS[request.model]

        params: Dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        if request.stop_sequences:
            params["stop"] = request.stop_sequences

        # Add any extra parameters
        params.update(request.extra_params)

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

            # Calculate cost
            cost_usd = self.calculate_cost(usage, request.model)

            return GenerationResult(
                provider=self.provider_name,
                model=request.model,
                prompt_text=request.prompt,
                completion_text=completion_text,
                usage=usage,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                raw_response={**response.model_dump(), "graybench_request": params},
                request_id=response.id if hasattr(response, "id") else None,
            )

        except OpenAIRateLimitError as e:
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
        pricing = MOONSHOT_PRICING.get(model)
        if not pricing:
            # Try to find a matching base model
            for base_model in sorted(MOONSHOT_PRICING, key=len, reverse=True):
                if model.startswith(base_model.split("-preview")[0]):
                    pricing = MOONSHOT_PRICING[base_model]
                    break

        if not pricing:
            # Default to kimi-k2.5 pricing
            return None

        input_cost = (usage.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

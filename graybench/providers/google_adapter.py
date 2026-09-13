"""
Google Gemini provider adapter.

Supports Gemini 1.5, 2.0, and upcoming Gemini 3 models.
"""

import os
from typing import Any, Dict, Optional

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

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

GOOGLE_PRICING = PRICING["google"]


class GoogleAdapter(ProviderAdapter):
    """
    Google Gemini API adapter.

    Supports the Generative AI API for all Gemini models.
    """

    provider_name = "google"

    supported_models = [
        "gemini-3-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the Google adapter.

        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        """
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        super().__init__(api_key=api_key, **kwargs)

        self.client = kwargs.get("client") or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=kwargs.get("timeout", 120) * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        start = self._time_request()
        request.validate_baseline(("thinking_config", "seed"))
        params = dict(
            temperature=request.temperature,
            top_p=request.top_p,
            max_output_tokens=request.max_tokens,
            candidate_count=1,
            automatic_function_calling={"disable": True},
            system_instruction=request.system_prompt,
            stop_sequences=request.stop_sequences or None,
            **request.extra_params,
        )
        try:
            response = self.client.models.generate_content(
                model=request.model,
                contents=request.prompt,
                config=types.GenerateContentConfig(**params),
            )
        except Exception as error:
            status = getattr(error, "code", None)
            if status == 429 and any(
                term in str(error).lower()
                for term in ("prepayment", "credits are depleted", "quota limit: 0")
            ):
                raise ProviderError(
                    "billing_or_quota_unavailable: " + str(error), self.provider_name, request.model
                ) from error
            if status == 404:
                raise ProviderError(
                    "model_not_found: " + str(error), self.provider_name, request.model
                ) from error
            if status == 429:
                raise RateLimitError(self.provider_name, details=str(error)) from error
            if status in (401, 403):
                raise AuthenticationError(
                    "Google authentication or permission denied", self.provider_name
                ) from error
            raise ProviderError(str(error), self.provider_name, request.model) from error
        metadata = response.usage_metadata
        usage = TokenUsage(
            input_tokens=getattr(metadata, "prompt_token_count", 0) or 0,
            output_tokens=(getattr(metadata, "candidates_token_count", 0) or 0)
            + (getattr(metadata, "thoughts_token_count", 0) or 0),
            reasoning_tokens=getattr(metadata, "thoughts_token_count", 0) or 0,
            cached_tokens=getattr(metadata, "cached_content_token_count", 0) or 0,
            total_tokens=getattr(metadata, "total_token_count", 0) or 0,
        )
        # Thinking text is never used as a fallback answer.
        text = "".join(
            part.text or ""
            for candidate in (response.candidates or [])[:1]
            for part in (getattr(candidate.content, "parts", None) or [])
            if not getattr(part, "thought", False)
        )
        raw = response.model_dump(mode="json")
        raw["graybench_request"] = {
            "model": request.model,
            "contents": request.prompt,
            "config": params,
        }
        return GenerationResult(
            provider=self.provider_name,
            model=request.model,
            prompt_text=request.prompt,
            completion_text=text,
            usage=usage,
            cost_usd=self.calculate_cost(usage, request.model) if metadata is not None else None,
            latency_ms=self._calculate_latency_ms(start),
            raw_response=raw,
        )

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        """
        Calculate the cost in USD.

        Args:
            usage: Token usage information
            model: Model identifier

        Returns:
            Cost in USD
        """
        pricing = GOOGLE_PRICING.get(model)
        if not pricing:
            return None
        tier = "_high" if usage.input_tokens > 200_000 and "input_high" in pricing else ""
        cached = min(usage.input_tokens, usage.cached_tokens)
        input_cost = (
            (usage.input_tokens - cached) * pricing["input" + tier]
            + cached * pricing["cached" + tier]
        ) / 1_000_000
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output" + tier]

        return input_cost + output_cost

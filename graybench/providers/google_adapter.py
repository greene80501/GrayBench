"""
Google Gemini provider adapter.

Supports Gemini 1.5, 2.0, and upcoming Gemini 3 models.
"""

import os
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
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
GOOGLE_PRICING = {
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-2.5-pro": {"input": 1.25, "input_high": 2.50, "output": 10.00, "output_high": 15.00},
    "gemini-2.5-flash": {"input": 0.30, "input_high": 0.60, "output": 2.50, "output_high": 5.00},
    "gemini-2.5-flash-lite": {"input": 0.10, "input_high": 0.20, "output": 0.40, "output_high": 0.80},
}


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
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the Google adapter.
        
        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
        """
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        super().__init__(api_key=api_key, **kwargs)
        
        genai.configure(api_key=api_key)
    
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
    )
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a completion using Google's Gemini API.
        
        Args:
            request: Generation request parameters
        
        Returns:
            GenerationResult with the completion
        """
        start_time = self._time_request()
        
        # Create model instance
        model = genai.GenerativeModel(
            model_name=request.model,
            system_instruction=request.system_prompt if request.system_prompt else None,
        )
        
        # Build generation config
        generation_config = GenerationConfig(
            temperature=request.temperature,
            top_p=request.top_p,
            max_output_tokens=request.max_tokens,
            stop_sequences=request.stop_sequences if request.stop_sequences else None,
        )
        
        try:
            response = model.generate_content(
                request.prompt,
                generation_config=generation_config,
            )
            
            latency_ms = self._calculate_latency_ms(start_time)
            
            # Extract completion text
            completion_text = ""
            if response.text:
                completion_text = response.text
            elif response.parts:
                completion_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
            
            # Extract usage from usage_metadata
            usage = TokenUsage()
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = TokenUsage(
                    input_tokens=getattr(response.usage_metadata, 'prompt_token_count', 0),
                    output_tokens=getattr(response.usage_metadata, 'candidates_token_count', 0),
                    total_tokens=getattr(response.usage_metadata, 'total_token_count', 0),
                )
            
            # Calculate cost
            cost_usd = self.calculate_cost(usage, request.model)
            
            # Build raw response dict
            raw_response = {
                "model": request.model,
                "text": completion_text,
                "usage": {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                },
            }
            
            # Add safety ratings if available
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                raw_response["prompt_feedback"] = str(response.prompt_feedback)
            
            return GenerationResult(
                provider=self.provider_name,
                model=request.model,
                prompt_text=request.prompt,
                completion_text=completion_text,
                usage=usage,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                raw_response=raw_response,
            )
            
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "quota" in error_str:
                raise RateLimitError(self.provider_name)
            if "api_key" in error_str or "authentication" in error_str or "invalid" in error_str:
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
        pricing = GOOGLE_PRICING.get(model)
        if not pricing:
            # Try to find a matching base model
            for base_model in GOOGLE_PRICING:
                if model.startswith(base_model.split('-latest')[0]):
                    pricing = GOOGLE_PRICING[base_model]
                    break
        
        if not pricing:
            # Default to Gemini 1.5 Pro pricing if unknown
            pricing = GOOGLE_PRICING["gemini-1.5-pro"]
        
        input_cost = (usage.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost

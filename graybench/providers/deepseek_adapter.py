"""
DeepSeek provider adapter.

DeepSeek provides an OpenAI-compatible API.
Supports DeepSeek Chat (V3.2) and DeepSeek Reasoner models.
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


# DeepSeek API base URL
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Pricing per 1M tokens
DEEPSEEK_PRICING = {
    "deepseek-chat": {"input": 0.28, "output": 0.42},
    "deepseek-reasoner": {"input": 0.28, "output": 0.42},
}


class DeepSeekAdapter(ProviderAdapter):
    """
    DeepSeek API adapter.
    
    Uses OpenAI-compatible API with custom base URL.
    """
    
    provider_name = "deepseek"
    
    supported_models = [
        "deepseek-chat",
        "deepseek-reasoner",
    ]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the DeepSeek adapter.
        
        Args:
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
            base_url: Optional custom base URL
        """
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        base_url = base_url or DEEPSEEK_BASE_URL
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
    
    @retry(
        retry=retry_if_exception_type(OpenAIRateLimitError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
    )
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a completion using DeepSeek's API.
        
        Args:
            request: Generation request parameters
        
        Returns:
            GenerationResult with the completion
        """
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
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
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
            
            # Handle reasoning tokens for deepseek-reasoner
            if hasattr(response.usage, 'completion_tokens_details') and response.usage.completion_tokens_details:
                if hasattr(response.usage.completion_tokens_details, 'reasoning_tokens'):
                    usage.reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens
            
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
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else {},
                request_id=response.id if hasattr(response, 'id') else None,
            )
            
        except OpenAIRateLimitError as e:
            raise RateLimitError(self.provider_name, retry_after=getattr(e, 'retry_after', None))
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
        pricing = DEEPSEEK_PRICING.get(model)
        if not pricing:
            # Default to deepseek-chat pricing
            pricing = DEEPSEEK_PRICING["deepseek-chat"]
        
        input_cost = (usage.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost

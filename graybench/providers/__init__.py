"""
Provider adapters for various LLM APIs.

Supports:
- OpenAI (GPT-4, GPT-4o, o1, future GPT-5.x)
- Anthropic (Claude 3.5, 4, 4.5)
- Google (Gemini 1.5, 2.0, 3)
- DeepSeek (Chat, Reasoner)
- Moonshot (Kimi K2, K2.5)
- GrayGate (local runs API)
"""

from typing import Optional
from graybench.config import get_global_config

from graybench.providers.base import (
    ProviderAdapter,
    GenerationRequest,
    GenerationResult,
    TokenUsage,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError,
    ContextLengthError,
)
from graybench.providers.openai_adapter import OpenAIAdapter, OPENAI_PRICING
from graybench.providers.anthropic_adapter import AnthropicAdapter, ANTHROPIC_PRICING
from graybench.providers.google_adapter import GoogleAdapter, GOOGLE_PRICING
from graybench.providers.deepseek_adapter import DeepSeekAdapter, DEEPSEEK_PRICING
from graybench.providers.moonshot_adapter import MoonshotAdapter, MOONSHOT_PRICING
from graybench.providers.graygate_adapter import GrayGateAdapter, GRAYGATE_PRICING


# Registry of available adapters
ADAPTER_REGISTRY = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "google": GoogleAdapter,
    "deepseek": DeepSeekAdapter,
    "moonshot": MoonshotAdapter,
    "graygate": GrayGateAdapter,
}

# Combined pricing dictionary for all providers
PRICING = {
    "openai": OPENAI_PRICING,
    "anthropic": ANTHROPIC_PRICING,
    "google": GOOGLE_PRICING,
    "deepseek": DEEPSEEK_PRICING,
    "moonshot": MOONSHOT_PRICING,
    "graygate": GRAYGATE_PRICING,
}


def get_adapter(
    provider: str,
    api_key: Optional[str] = None,
    **kwargs
) -> ProviderAdapter:
    """
    Get a provider adapter by name.
    
    Args:
        provider: Provider name (openai, anthropic, google, deepseek, moonshot)
        api_key: Optional API key (otherwise loaded from environment)
        **kwargs: Additional provider-specific options
    
    Returns:
        Configured ProviderAdapter instance
    
    Raises:
        ValueError: If provider is not supported
    """
    provider = provider.lower()
    
    if provider not in ADAPTER_REGISTRY:
        available = ", ".join(ADAPTER_REGISTRY.keys())
        raise ValueError(f"Unknown provider '{provider}'. Available: {available}")
    
    adapter_class = ADAPTER_REGISTRY[provider]
    
    if api_key is None:
        config = get_global_config()
        provider_config = config.get_provider(provider)
        if provider_config and provider_config.api_key:
            api_key = provider_config.api_key

    return adapter_class(api_key=api_key, **kwargs)


def list_providers() -> list[str]:
    """List all available provider names."""
    return list(ADAPTER_REGISTRY.keys())


def get_pricing(provider: str, model: str) -> dict:
    """
    Get pricing information for a specific provider and model.
    
    Args:
        provider: Provider name
        model: Model identifier
    
    Returns:
        Dictionary with 'input' and 'output' prices per 1M tokens
    """
    provider_pricing = PRICING.get(provider.lower(), {})
    return provider_pricing.get(model, {"input": 0.0, "output": 0.0})


__all__ = [
    # Base classes
    "ProviderAdapter",
    "GenerationRequest",
    "GenerationResult",
    "TokenUsage",
    # Exceptions
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotFoundError",
    "ContextLengthError",
    # Adapters
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GoogleAdapter",
    "DeepSeekAdapter",
    "MoonshotAdapter",
    "GrayGateAdapter",
    # Factory
    "get_adapter",
    "list_providers",
    "get_pricing",
    # Pricing
    "PRICING",
    "ADAPTER_REGISTRY",
]

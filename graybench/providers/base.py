"""
Base classes for provider adapters.

All provider-specific adapters inherit from ProviderAdapter and implement
the generate() method to produce GenerationResult objects.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TokenUsage:
    """Token usage information from an API call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0  # Some providers have cached token pricing
    reasoning_tokens: int = 0  # For models with thinking/reasoning output

    def __post_init__(self):
        """Calculate total if not provided."""
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class GenerationRequest:
    """Request parameters for model generation."""

    prompt: str
    model: str
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 16384
    stop_sequences: List[str] = field(default_factory=list)
    system_prompt: Optional[str] = None

    # Additional parameters for specific providers
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def validate_baseline(self, allowed_extras=()):
        unknown = set(self.extra_params) - set(allowed_extras)
        if unknown:
            raise ValueError(f"Unsupported baseline parameters: {sorted(unknown)}")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")


@dataclass
class GenerationResult:
    """Result from a model generation call."""

    # Provider and model info
    provider: str
    model: str

    # Content
    prompt_text: str
    completion_text: str

    # Usage and cost
    usage: TokenUsage
    cost_usd: Optional[float]

    # Performance metrics
    latency_ms: float

    # Raw API response for auditing
    raw_response: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: Optional[str] = None

    # Error information (if any)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if the generation was successful."""
        return self.error is None and bool(self.completion_text)


class ProviderAdapter(ABC):
    """
    Abstract base class for provider adapters.

    Each provider (OpenAI, Anthropic, etc.) implements this interface
    to provide a unified way to generate completions.
    """

    # Provider name (e.g., "openai", "anthropic")
    provider_name: str = "base"

    # Supported models for this provider
    supported_models: List[str] = []

    # Default generation parameters
    default_temperature: float = 0.0
    default_max_tokens: int = 16384

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        """
        Initialize the adapter.

        Args:
            api_key: API key for the provider
            base_url: Optional custom base URL
            **kwargs: Additional provider-specific options
        """
        self.api_key = api_key
        self.base_url = base_url
        self.extra_options = kwargs

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a completion for the given request.

        Args:
            request: The generation request parameters

        Returns:
            GenerationResult with the completion and metadata
        """
        pass

    @abstractmethod
    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        """
        Calculate the cost in USD for the given usage.

        Args:
            usage: Token usage information
            model: Model identifier

        Returns:
            Cost in USD
        """
        pass

    def is_model_supported(self, model: str) -> bool:
        """Check if a model is supported by this adapter."""
        return model in self.supported_models

    def _time_request(self):
        """Context manager-like helper for timing requests."""
        return time.perf_counter()

    def _calculate_latency_ms(self, start_time: float) -> float:
        """Calculate latency in milliseconds."""
        return (time.perf_counter() - start_time) * 1000


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, message: str, provider: str, model: str = None):
        self.message = message
        self.provider = provider
        self.model = model
        super().__init__(f"[{provider}] {message}")


class RateLimitError(ProviderError):
    """Raised when hitting API rate limits."""

    def __init__(self, provider: str, retry_after: Optional[float] = None, details: str = ""):
        self.retry_after = retry_after
        message = f"Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        if details:
            message += ": " + details
        super().__init__(message, provider)


class AuthenticationError(ProviderError):
    """Raised when API authentication fails."""

    pass


class ModelNotFoundError(ProviderError):
    """Raised when the requested model is not found."""

    pass


class ContextLengthError(ProviderError):
    """Raised when the context length is exceeded."""

    def __init__(self, provider: str, model: str, tokens: int, limit: int):
        self.tokens = tokens
        self.limit = limit
        message = f"Context length {tokens} exceeds limit {limit}"
        super().__init__(message, provider, model)

"""
Configuration management for graybench.

Handles loading environment variables, provider settings, and runtime configuration.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""
    
    name: str
    api_key_env: str
    base_url: str
    models: list[str]
    default_params: dict[str, Any] = field(default_factory=dict)
    max_context_tokens: int = 128000
    supports_temperature_zero: bool = True
    
    @property
    def api_key(self) -> Optional[str]:
        """Get the API key from environment."""
        return os.getenv(self.api_key_env)
    
    @property
    def is_configured(self) -> bool:
        """Check if the provider has an API key configured."""
        if self.name.lower() == "graygate":
            return bool(self.api_key) or bool(os.getenv("GRAYGATE_ADMIN_SECRET"))
        return bool(self.api_key)


@dataclass
class ExecutionConfig:
    """Configuration for code execution."""
    
    timeout_seconds: int = 500
    max_memory_mb: int = 4096
    max_output_bytes: int = 1024 * 1024  # 1MB
    isolate_processes: bool = True
    capture_stdout: bool = True
    capture_stderr: bool = True


@dataclass  
class GenerationConfig:
    """Configuration for model generation."""
    
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 4096
    n_samples: int = 1
    stop_sequences: list[str] = field(default_factory=list)


@dataclass
class Config:
    """Main configuration class for graybench."""
    
    # Paths
    base_dir: Path = field(default_factory=lambda: Path.cwd())
    db_path: Path = field(default_factory=lambda: Path("./data/graybench.db"))
    results_dir: Path = field(default_factory=lambda: Path("./results"))
    
    # Provider configurations
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    
    # Execution settings
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    
    # Generation settings
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    
    # Runtime settings
    workers: int = 4
    debug: bool = False
    
    # IBM Quantum settings
    ibm_quantum_token: Optional[str] = None
    ibm_quantum_channel: str = "ibm_quantum"
    ibm_quantum_instance: Optional[str] = None
    
    def __post_init__(self):
        """Ensure paths are Path objects."""
        if isinstance(self.base_dir, str):
            self.base_dir = Path(self.base_dir)
        if isinstance(self.db_path, str):
            self.db_path = Path(self.db_path)
        if isinstance(self.results_dir, str):
            self.results_dir = Path(self.results_dir)
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get a provider configuration by name."""
        return self.providers.get(name.lower())
    
    def list_configured_providers(self) -> list[str]:
        """List all providers that have API keys configured."""
        return [name for name, config in self.providers.items() if config.is_configured]
    
    def list_all_models(self) -> list[tuple[str, str]]:
        """List all available models as (provider, model) tuples."""
        models = []
        for provider_name, config in self.providers.items():
            for model in config.models:
                models.append((provider_name, model))
        return models


# Default provider configurations
DEFAULT_PROVIDERS = {
    "openai": ProviderConfig(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        models=[
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
        ],
        default_params={},
        max_context_tokens=128000,
    ),
    "anthropic": ProviderConfig(
        name="anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com",
        models=[
            "claude-opus-4-5-20251101",
            "claude-sonnet-4-5-20250929",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-1-20250805",
            "claude-opus-4-20250514",
            "claude-sonnet-4-20250514",
        ],
        default_params={},
        max_context_tokens=200000,
    ),
    "google": ProviderConfig(
        name="google",
        api_key_env="GOOGLE_API_KEY",
        base_url="https://generativelanguage.googleapis.com",
        models=[
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
        default_params={},
        max_context_tokens=1000000,
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        models=[
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        default_params={},
        max_context_tokens=64000,
    ),
    "moonshot": ProviderConfig(
        name="moonshot",
        api_key_env="MOONSHOT_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        models=[
            "kimi-k2.5",
            "kimi-k2-thinking",
            "kimi-k2-turbo-preview",
        ],
        default_params={},
        max_context_tokens=131072,
    ),
    "graygate": ProviderConfig(
        name="graygate",
        api_key_env="GRAYGATE_API_KEY",
        base_url="http://localhost:8000",
        models=[
            "graygate",
        ],
        default_params={},
        max_context_tokens=128000,
    ),
}


def load_providers_from_yaml(yaml_path: Path) -> dict[str, ProviderConfig]:
    """Load provider configurations from a YAML file."""
    if not yaml_path.exists():
        return {}
    
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    
    providers = {}
    for name, config in data.get("providers", {}).items():
        providers[name] = ProviderConfig(
            name=name,
            api_key_env=config.get("api_key_env", f"{name.upper()}_API_KEY"),
            base_url=config.get("base_url", ""),
            models=config.get("models", []),
            default_params=config.get("default_params", {}),
            max_context_tokens=config.get("max_context_tokens", 128000),
            supports_temperature_zero=config.get("supports_temperature_zero", True),
        )
    
    return providers


def get_config(
    config_path: Optional[Path] = None,
    env_file: Optional[Path] = None,
) -> Config:
    """
    Load and return the configuration.
    
    Args:
        config_path: Path to providers.yaml configuration file
        env_file: Path to .env file
    
    Returns:
        Configured Config instance
    """
    # Load environment variables
    if env_file and env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()  # Try default .env
    
    # Start with default providers
    providers = DEFAULT_PROVIDERS.copy()
    
    # Override with YAML config if provided
    if config_path and config_path.exists():
        yaml_providers = load_providers_from_yaml(config_path)
        providers.update(yaml_providers)
    
    # Load paths from environment
    db_path = Path(os.getenv("GRAYBENCH_DB_PATH", "./data/graybench.db"))
    results_dir = Path(os.getenv("GRAYBENCH_RESULTS_DIR", "./results"))
    
    # Load execution settings from environment
    execution = ExecutionConfig(
        timeout_seconds=int(os.getenv("GRAYBENCH_EXEC_TIMEOUT", "120")),
    )
    
    # Load runtime settings from environment
    workers = int(os.getenv("GRAYBENCH_WORKERS", "4"))
    debug = os.getenv("GRAYBENCH_DEBUG", "false").lower() in ("true", "1", "yes")
    
    # Load IBM Quantum settings
    ibm_quantum_token = os.getenv("IBM_QUANTUM_TOKEN")
    ibm_quantum_channel = os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum")
    ibm_quantum_instance = os.getenv("IBM_QUANTUM_INSTANCE")
    
    return Config(
        db_path=db_path,
        results_dir=results_dir,
        providers=providers,
        execution=execution,
        workers=workers,
        debug=debug,
        ibm_quantum_token=ibm_quantum_token,
        ibm_quantum_channel=ibm_quantum_channel,
        ibm_quantum_instance=ibm_quantum_instance,
    )


# Global configuration instance (lazy loaded)
_config: Optional[Config] = None


def get_global_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = get_config()
    return _config


def set_global_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


def list_all_providers() -> list[str]:
    """List all available provider names."""
    return list(DEFAULT_PROVIDERS.keys())


# Convenience function for Config
Config.list_all_providers = staticmethod(list_all_providers)


# Pricing data (imported from providers for convenience)
# This allows config to be imported without pulling in provider implementations
PRICING = {
    "openai": {
        "gpt-5.2": {"input": 1.75, "output": 14.00},
        "gpt-5.2-pro": {"input": 21.00, "output": 168.00},
        "gpt-5.1": {"input": 1.25, "output": 10.00},
        "gpt-5-mini": {"input": 0.25, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "output": 0.40},
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "o3": {"input": 2.00, "output": 8.00},
        "o3-pro": {"input": 20.00, "output": 80.00},
        "o4-mini": {"input": 1.10, "output": 4.40},
        "o1": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 1.10, "output": 4.40},
        "o1-pro": {"input": 150.00, "output": 600.00},
    },
    "anthropic": {
        "claude-opus-4-5-20251101": {"input": 5.00, "output": 25.00},
        "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
        "claude-opus-4-1-20250805": {"input": 15.00, "output": 75.00},
        "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    },
    "google": {
        "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
        "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
        "gemini-2.5-pro": {"input": 1.25, "input_high": 2.50, "output": 10.00, "output_high": 15.00},
        "gemini-2.5-flash": {"input": 0.30, "input_high": 0.60, "output": 2.50, "output_high": 5.00},
        "gemini-2.5-flash-lite": {"input": 0.10, "input_high": 0.20, "output": 0.40, "output_high": 0.80},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.28, "output": 0.42},
        "deepseek-reasoner": {"input": 0.28, "output": 0.42},
    },
    "moonshot": {
        "kimi-k2.5": {"input": 0.60, "output": 3.00},
        "kimi-k2-thinking": {"input": 0.60, "output": 2.50},
        "kimi-k2-turbo-preview": {"input": 1.15, "output": 8.00},
    },
    "graygate": {
        "graygate": {"input": 0.0, "output": 0.0},
    },
}

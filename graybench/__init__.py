"""
Gray Area Labs Benchmark Suite (graybench)

A comprehensive benchmark suite for evaluating LLM performance on Qiskit HumanEval tasks.
Supports multiple providers (OpenAI, Anthropic, Google, DeepSeek, Moonshot, GrayGate) with
fair, reproducible evaluation methodology.
"""

__version__ = "2.0.0"
__author__ = "Gray Area Labs"

from graybench.config import Config, get_config, PRICING
from graybench.dataset.loader import DatasetLoader
from graybench.dataset.models import Task, TaskDifficulty, SuiteType
from graybench.execution.harness import ExecutionHarness, ExecutionResult
from graybench.execution.outcomes import Outcome, OutcomeCategory
from graybench.storage.database import Database, ResultStorage
from graybench.providers.base import (
    ProviderAdapter,
    GenerationResult,
    GenerationRequest,
    TokenUsage,
)
from graybench.providers import get_adapter, list_providers

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Configuration
    "Config",
    "get_config",
    "PRICING",
    # Dataset
    "DatasetLoader",
    "Task",
    "TaskDifficulty",
    "SuiteType",
    # Execution
    "ExecutionHarness",
    "ExecutionResult",
    "Outcome",
    "OutcomeCategory",
    # Storage
    "Database",
    "ResultStorage",
    # Providers
    "ProviderAdapter",
    "GenerationResult",
    "GenerationRequest",
    "TokenUsage",
    "get_adapter",
    "list_providers",
]

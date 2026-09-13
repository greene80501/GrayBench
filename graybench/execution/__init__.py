"""
Execution module for running and evaluating code solutions.

Provides:
- ExecutionHarness: Isolated code execution
- CodeExtractor: Extract code from model outputs
- Outcome: Detailed outcome categories
"""

from graybench.execution.outcomes import Outcome, OutcomeCategory
from graybench.execution.code_extractor import (
    CodeExtractor,
    ExtractionResult,
    extract_code,
)
from graybench.execution.harness import (
    ExecutionHarness,
    ExecutionResult,
)

__all__ = [
    # Outcomes
    "Outcome",
    "OutcomeCategory",
    # Code extraction
    "CodeExtractor",
    "ExtractionResult",
    "extract_code",
    # Execution
    "ExecutionHarness",
    "ExecutionResult",
]

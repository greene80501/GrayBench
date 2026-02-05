"""
Data models for benchmark tasks.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskDifficulty(Enum):
    """Task difficulty levels from the Qiskit HumanEval dataset."""
    
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_string(cls, value: str) -> "TaskDifficulty":
        """Parse difficulty from string."""
        value = value.lower().strip()
        for difficulty in cls:
            if difficulty.value == value:
                return difficulty
        return cls.UNKNOWN


class SuiteType(Enum):
    """Benchmark suite types."""
    
    NORMAL = "normal"
    HARD = "hard"


@dataclass
class Task:
    """
    Represents a single benchmark task.
    
    Attributes:
        task_id: Unique identifier for the task (e.g., "qiskitHumanEval/48")
        prompt: The prompt text to give to the model
        entry_point: The function name that must be implemented
        test: The test code that validates the solution
        canonical_solution: The reference solution (for validation)
        difficulty: Task difficulty level
        suite: Which suite this task belongs to (normal or hard)
        metadata: Additional metadata from the dataset
    """
    
    task_id: str
    prompt: str
    entry_point: str
    test: str
    canonical_solution: str
    difficulty: TaskDifficulty = TaskDifficulty.UNKNOWN
    suite: SuiteType = SuiteType.NORMAL
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def task_number(self) -> int:
        """Extract the numeric task ID."""
        try:
            # Handle formats like "qiskitHumanEval/48" or just "48"
            if "/" in self.task_id:
                return int(self.task_id.split("/")[-1])
            return int(self.task_id)
        except (ValueError, IndexError):
            return -1
    
    @property
    def short_id(self) -> str:
        """Get a short version of the task ID."""
        if "/" in self.task_id:
            return self.task_id.split("/")[-1]
        return self.task_id
    
    def get_prompt_for_model(self, include_hints: bool = True) -> str:
        """
        Get the prompt to send to the model.
        
        For 'hard' suite tasks, this returns just the raw prompt with no hints.
        For 'normal' suite tasks, this includes any provided context.
        
        Args:
            include_hints: Whether to include any hints or context (ignored for hard suite)
        
        Returns:
            The prompt string for the model
        """
        if self.suite == SuiteType.HARD:
            # Hard mode: raw problem statement only, no imports or signatures
            return self.prompt
        
        # Normal mode: include the full prompt as-is
        return self.prompt
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "entry_point": self.entry_point,
            "test": self.test,
            "canonical_solution": self.canonical_solution,
            "difficulty": self.difficulty.value,
            "suite": self.suite.value,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create a Task from a dictionary."""
        return cls(
            task_id=data["task_id"],
            prompt=data["prompt"],
            entry_point=data["entry_point"],
            test=data["test"],
            canonical_solution=data.get("canonical_solution", ""),
            difficulty=TaskDifficulty.from_string(data.get("difficulty", "unknown")),
            suite=SuiteType(data.get("suite", "normal")),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TaskAttempt:
    """
    Represents a single attempt at solving a task.
    
    Attributes:
        task: The task being attempted
        model_output: Raw output from the model
        extracted_code: Code extracted from model output
        execution_result: Result of running the code
        tokens_prompt: Number of prompt tokens used
        tokens_completion: Number of completion tokens used
        cost_usd: Cost of this attempt in USD
        latency_ms: Time taken for generation in milliseconds
    """
    
    task: Task
    model_output: str
    extracted_code: Optional[str] = None
    execution_result: Optional["ExecutionResult"] = None
    tokens_prompt: int = 0
    tokens_completion: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    
    @property
    def passed(self) -> bool:
        """Check if this attempt passed all tests."""
        if self.execution_result is None:
            return False
        return self.execution_result.passed


@dataclass
class ExecutionResult:
    """
    Result of executing a code solution.
    
    Attributes:
        passed: Whether all tests passed
        outcome: Detailed outcome category
        stdout: Captured standard output
        stderr: Captured standard error
        error_type: Type of error if any (e.g., "SyntaxError")
        error_message: Error message if any
        execution_time_ms: Time taken to execute in milliseconds
    """
    
    passed: bool
    outcome: str  # Will be OutcomeCategory value
    stdout: str = ""
    stderr: str = ""
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "passed": self.passed,
            "outcome": self.outcome,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
        }

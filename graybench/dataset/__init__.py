"""
Dataset loading and management for graybench.
"""

from graybench.dataset.loader import DatasetLoader, load_qiskit_humaneval
from graybench.dataset.models import (
    Task,
    TaskDifficulty,
    TaskAttempt,
    SuiteType,
)


class Dataset:
    """Wrapper class for a loaded dataset."""
    
    def __init__(
        self,
        tasks: list,
        suite: str,
        version: str = "1.0.0",
        source: str = "huggingface",
    ):
        self.tasks = tasks
        self.suite = suite
        self.version = version
        self.source = source
        self._hash = None
    
    def __len__(self):
        return len(self.tasks)
    
    def __iter__(self):
        return iter(self.tasks)
    
    @property
    def name(self) -> str:
        return f"Qiskit HumanEval ({self.suite})"
    
    @property
    def dataset_hash(self) -> str:
        if self._hash is None:
            import hashlib
            content = "".join(f"{t.task_id}:{t.prompt[:50]}" for t in self.tasks)
            self._hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return self._hash


# Add convenience methods to DatasetLoader
_original_load_tasks = DatasetLoader.load_tasks


def _load_wrapper(self, suite):
    """Load tasks and return a Dataset object."""
    suite_type = suite if isinstance(suite, SuiteType) else (
        SuiteType.HARD if str(suite).lower() == "hard" else SuiteType.NORMAL
    )
    tasks = _original_load_tasks(self, suite_type)
    return Dataset(
        tasks=tasks,
        suite=suite_type.value,
        version=self.dataset_version,
        source="huggingface",
    )


def load(self, suite: str = "normal") -> Dataset:
    """Load a dataset by suite name."""
    return _load_wrapper(self, suite)


def get_difficulty_distribution(self, dataset) -> dict:
    """Get difficulty distribution for a dataset."""
    dist = {}
    for task in dataset.tasks:
        level = task.difficulty.value
        dist[level] = dist.get(level, 0) + 1
    return dist


def analyze_imports(self, dataset) -> dict:
    """Analyze imports used in a dataset."""
    import_counts = {}
    for task in dataset.tasks:
        for line in (task.prompt + "\n" + task.canonical_solution).split('\n'):
            stripped = line.strip()
            if stripped.startswith("import "):
                module = stripped[7:].split()[0].split(".")[0]
                import_counts[module] = import_counts.get(module, 0) + 1
            elif stripped.startswith("from "):
                parts = stripped[5:].split()
                if parts:
                    module = parts[0].split(".")[0]
                    import_counts[module] = import_counts.get(module, 0) + 1
    return dict(sorted(import_counts.items(), key=lambda x: x[1], reverse=True))


DatasetLoader.load = load
DatasetLoader.get_difficulty_distribution = get_difficulty_distribution
DatasetLoader.analyze_imports = analyze_imports


__all__ = [
    "DatasetLoader",
    "Dataset",
    "load_qiskit_humaneval",
    "Task",
    "TaskDifficulty",
    "TaskAttempt",
    "SuiteType",
]

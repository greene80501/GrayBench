"""
Dataset loader for Qiskit HumanEval benchmark.

Loads tasks from the HuggingFace datasets repository.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Iterator, Optional

from huggingface_hub import hf_hub_download
import pyarrow.parquet as parquet

from graybench.dataset.models import Task, TaskDifficulty, SuiteType

logger = logging.getLogger(__name__)


# HuggingFace dataset identifiers
DATASET_NORMAL = "Qiskit/qiskit_humaneval"
DATASET_HARD = "Qiskit/qiskit_humaneval_hard"

# Immutable upstream revisions. Updates require a new environment validation.
DATASET_REVISIONS = {
    SuiteType.NORMAL: "a0066805f7a15cb48e9d0cface2210056185be6d",
    SuiteType.HARD: "315e167a479d5c546565d7f9f8c63a644c84cb50",
}


class DatasetLoader:
    """
    Loader for Qiskit HumanEval datasets.

    Supports loading both normal and hard versions of the benchmark
    from HuggingFace datasets.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        offline: bool = False,
    ):
        """
        Initialize the dataset loader.

        Args:
            cache_dir: Directory to cache downloaded datasets
            offline: If True, only use cached data
        """
        self.cache_dir = cache_dir or Path("data/datasets")
        self.offline = offline
        self._normal_tasks: Optional[list[Task]] = None
        self._hard_tasks: Optional[list[Task]] = None

    @property
    def dataset_version(self) -> str:
        """Identify both pinned dataset revisions; per-suite content hashes are on Dataset."""
        content = {suite.value: revision for suite, revision in DATASET_REVISIONS.items()}
        return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()

    def load_tasks(self, suite: SuiteType) -> list[Task]:
        """
        Load all tasks for a given suite.

        Args:
            suite: Which suite to load (normal or hard)

        Returns:
            List of Task objects
        """
        suite = SuiteType(suite)
        if suite == SuiteType.NORMAL:
            if self._normal_tasks is None:
                self._normal_tasks = self._load_pinned_tasks(suite)
            return self._normal_tasks
        else:
            if self._hard_tasks is None:
                self._hard_tasks = self._load_pinned_tasks(suite)
            return self._hard_tasks

    def _load_pinned_tasks(self, suite: SuiteType) -> list[Task]:
        source = DATASET_NORMAL if suite == SuiteType.NORMAL else DATASET_HARD
        # Read pinned Parquet directly, avoiding datasets' long generated cache paths on Windows.
        path = hf_hub_download(
            repo_id=source,
            repo_type="dataset",
            revision=DATASET_REVISIONS[suite],
            filename="data/test-00000-of-00001.parquet",
            local_dir=self.cache_dir / suite.value / DATASET_REVISIONS[suite][:12],
            local_files_only=self.offline,
        )
        rows = parquet.read_table(path).to_pylist()
        tasks = [self._parse_task_item(row, suite, i) for i, row in enumerate(rows)]
        if not tasks or len({task.task_id for task in tasks}) != len(tasks):
            raise ValueError("Dataset is empty or contains duplicate task IDs")
        for task in tasks:
            if not all((task.prompt, task.entry_point, task.test, task.canonical_solution)):
                raise ValueError(f"Missing required fields in {task.task_id}")
        return tasks

    def _parse_task_item(self, item: dict, suite: SuiteType, index: int) -> Task:
        """Parse a single dataset item into a Task object."""
        # Handle different field naming conventions
        task_id = item.get("task_id") or item.get("id") or f"qiskitHumanEval/{index}"
        prompt = item.get("prompt") or item.get("question") or ""
        entry_point = item.get("entry_point") or item.get("function_name") or ""
        test = item.get("test") or item.get("tests") or item.get("test_code") or ""
        canonical_solution = (
            item.get("canonical_solution")
            or item.get("solution")
            or item.get("reference_solution")
            or ""
        )

        # Parse difficulty
        difficulty_str = (
            item.get("difficulty_scale") or item.get("difficulty") or item.get("level") or "unknown"
        )
        difficulty = TaskDifficulty.from_string(str(difficulty_str))

        # Collect any extra metadata
        metadata = {}
        extra_fields = ["tags", "category", "concepts", "qiskit_version", "imports"]
        for field in extra_fields:
            if field in item and item[field]:
                metadata[field] = item[field]

        return Task(
            task_id=task_id,
            prompt=prompt,
            entry_point=entry_point,
            test=test,
            canonical_solution=canonical_solution,
            difficulty=difficulty,
            suite=suite,
            metadata=metadata,
        )

    def get_task_by_id(self, task_id: str, suite: SuiteType) -> Optional[Task]:
        """
        Get a specific task by ID.

        Args:
            task_id: The task ID to look for
            suite: Which suite to search

        Returns:
            The Task if found, None otherwise
        """
        tasks = self.load_tasks(suite)
        for task in tasks:
            if task.task_id == task_id or task.short_id == task_id:
                return task
        return None

    def iter_tasks(self, suite: SuiteType) -> Iterator[Task]:
        """
        Iterate over all tasks in a suite.

        Args:
            suite: Which suite to iterate

        Yields:
            Task objects
        """
        yield from self.load_tasks(suite)

    def get_task_count(self, suite: SuiteType) -> int:
        """Get the number of tasks in a suite."""
        return len(self.load_tasks(suite))

    def get_difficulty_distribution(self, suite: SuiteType) -> dict[TaskDifficulty, int]:
        """Get count of tasks by difficulty level."""
        tasks = self.load_tasks(suite)
        distribution = {}
        for task in tasks:
            distribution[task.difficulty] = distribution.get(task.difficulty, 0) + 1
        return distribution

    def analyze_imports(self, suite: SuiteType) -> dict[str, int]:
        """
        Analyze which imports are used across all tasks.

        Returns a dictionary mapping import names to count of tasks using them.
        """
        tasks = self.load_tasks(suite)
        import_counts = {}

        for task in tasks:
            # Check prompt for imports
            for line in task.prompt.split("\n"):
                stripped = line.strip()
                if stripped.startswith("import "):
                    module = stripped[7:].split()[0].split(".")[0]
                    import_counts[module] = import_counts.get(module, 0) + 1
                elif stripped.startswith("from "):
                    parts = stripped[5:].split()
                    if parts:
                        module = parts[0].split(".")[0]
                        import_counts[module] = import_counts.get(module, 0) + 1

            # Also check canonical solution
            for line in task.canonical_solution.split("\n"):
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

    def export_to_jsonl(self, suite: SuiteType, output_path: Path) -> None:
        """
        Export tasks to a JSONL file.

        Args:
            suite: Which suite to export
            output_path: Path to write the JSONL file
        """
        tasks = self.load_tasks(suite)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(task.to_dict()) + "\n")

        logger.info(f"Exported {len(tasks)} tasks to {output_path}")


# Convenience function for quick access
def load_qiskit_humaneval(
    suite: str = "normal",
    cache_dir: Optional[Path] = None,
) -> list[Task]:
    """
    Load the Qiskit HumanEval dataset.

    Args:
        suite: Either "normal" or "hard"
        cache_dir: Optional cache directory

    Returns:
        List of Task objects
    """
    loader = DatasetLoader(cache_dir=cache_dir)
    suite_type = SuiteType(suite.lower())
    return loader.load_tasks(suite_type)

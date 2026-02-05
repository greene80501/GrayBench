"""
Dataset loader for Qiskit HumanEval benchmark.

Loads tasks from the HuggingFace datasets repository.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Iterator, Optional

from datasets import load_dataset

from graybench.dataset.models import Task, TaskDifficulty, SuiteType


logger = logging.getLogger(__name__)


# HuggingFace dataset identifiers
DATASET_NORMAL = "Qiskit/qiskit_humaneval"
DATASET_HARD = "Qiskit/qiskit_humaneval_hard"

# Alternative dataset paths (if the main ones change)
DATASET_NORMAL_ALT = "ibm-research/qiskit-humaneval"
DATASET_HARD_ALT = "ibm-research/qiskit-humaneval-hard"


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
        self.cache_dir = cache_dir
        self.offline = offline
        self._normal_tasks: Optional[list[Task]] = None
        self._hard_tasks: Optional[list[Task]] = None
        self._dataset_version: Optional[str] = None
    
    @property
    def dataset_version(self) -> str:
        """Get a hash representing the dataset version."""
        if self._dataset_version is None:
            # Compute hash from task IDs and prompts
            tasks = self.load_tasks(SuiteType.NORMAL)
            content = "".join(f"{t.task_id}:{t.prompt[:100]}" for t in tasks)
            self._dataset_version = hashlib.sha256(content.encode()).hexdigest()[:12]
        return self._dataset_version
    
    def load_tasks(self, suite: SuiteType) -> list[Task]:
        """
        Load all tasks for a given suite.
        
        Args:
            suite: Which suite to load (normal or hard)
        
        Returns:
            List of Task objects
        """
        if suite == SuiteType.NORMAL:
            if self._normal_tasks is None:
                self._normal_tasks = self._load_normal_tasks()
            return self._normal_tasks
        else:
            if self._hard_tasks is None:
                self._hard_tasks = self._load_hard_tasks()
            return self._hard_tasks
    
    def _load_normal_tasks(self) -> list[Task]:
        """Load the normal (standard) version of the dataset."""
        logger.info(f"Loading normal dataset from HuggingFace: {DATASET_NORMAL}")
        
        try:
            dataset = load_dataset(
                DATASET_NORMAL,
                split="test",
                cache_dir=str(self.cache_dir) if self.cache_dir else None,
            )
        except Exception as e:
            logger.warning(f"Failed to load from {DATASET_NORMAL}: {e}")
            logger.info(f"Trying alternative: {DATASET_NORMAL_ALT}")
            dataset = load_dataset(
                DATASET_NORMAL_ALT,
                split="test",
                cache_dir=str(self.cache_dir) if self.cache_dir else None,
            )
        
        tasks = []
        for idx, item in enumerate(dataset):
            task = self._parse_task_item(item, SuiteType.NORMAL, idx)
            tasks.append(task)
        
        logger.info(f"Loaded {len(tasks)} normal tasks")
        return tasks
    
    def _load_hard_tasks(self) -> list[Task]:
        """Load the hard version of the dataset."""
        logger.info(f"Loading hard dataset from HuggingFace: {DATASET_HARD}")
        
        try:
            dataset = load_dataset(
                DATASET_HARD,
                split="test",
                cache_dir=str(self.cache_dir) if self.cache_dir else None,
            )
        except Exception as e:
            logger.warning(f"Failed to load from {DATASET_HARD}: {e}")
            # Try alternate hard dataset repo
            try:
                dataset = load_dataset(
                    DATASET_HARD_ALT,
                    split="test",
                    cache_dir=str(self.cache_dir) if self.cache_dir else None,
                )
            except Exception:
                # Try loading from the same repo with a different config/split
                try:
                    dataset = load_dataset(
                        DATASET_NORMAL,  # Same repo, different config
                        "hard",
                        split="test",
                        cache_dir=str(self.cache_dir) if self.cache_dir else None,
                    )
                except Exception:
                    logger.warning("Hard dataset not found as separate config")
                    # Final fallback: use normal but strip hints
                    logger.info("Generating hard prompts from normal dataset")
                    return self._generate_hard_from_normal()
        
        tasks = []
        for idx, item in enumerate(dataset):
            task = self._parse_task_item(item, SuiteType.HARD, idx)
            tasks.append(task)
        
        logger.info(f"Loaded {len(tasks)} hard tasks")
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
        difficulty_str = item.get("difficulty") or item.get("level") or "unknown"
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
    
    def _generate_hard_from_normal(self) -> list[Task]:
        """
        Generate hard prompts from normal tasks by stripping hints.
        
        This is a fallback if the hard dataset isn't separately available.
        The hard version should only contain the problem description without
        any imports, function signatures, or other hints.
        """
        normal_tasks = self.load_tasks(SuiteType.NORMAL)
        hard_tasks = []
        
        for task in normal_tasks:
            # Create a hard version with stripped prompt
            hard_prompt = self._strip_hints_from_prompt(task.prompt)
            
            hard_task = Task(
                task_id=task.task_id,
                prompt=hard_prompt,
                entry_point=task.entry_point,
                test=task.test,
                canonical_solution=task.canonical_solution,
                difficulty=task.difficulty,
                suite=SuiteType.HARD,
                metadata=task.metadata.copy(),
            )
            hard_tasks.append(hard_task)
        
        return hard_tasks
    
    def _strip_hints_from_prompt(self, prompt: str) -> str:
        """
        Strip hints from a prompt to create a 'hard' version.
        
        Removes:
        - Import statements
        - Function signatures
        - Type hints
        - Docstring templates
        
        Keeps:
        - The actual problem description
        """
        lines = prompt.split("\n")
        filtered_lines = []
        in_docstring = False
        found_description = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip import statements
            if stripped.startswith("import ") or stripped.startswith("from "):
                continue
            
            # Skip function definition
            if stripped.startswith("def "):
                continue
            
            # Track docstrings
            if '"""' in stripped or "'''" in stripped:
                quote = '"""' if '"""' in stripped else "'''"
                count = stripped.count(quote)
                if count == 2:
                    # Single-line docstring - extract content
                    content = stripped.split(quote)[1].strip()
                    if content:
                        filtered_lines.append(content)
                        found_description = True
                    continue
                elif count == 1:
                    in_docstring = not in_docstring
                    if not in_docstring and found_description:
                        continue
                    continue
            
            # Collect content inside docstring (the actual description)
            if in_docstring:
                if stripped and not stripped.startswith(":param") and not stripped.startswith(":return"):
                    filtered_lines.append(stripped)
                    found_description = True
                continue
            
            # Skip type hints and return statements
            if stripped.startswith("->") or stripped.startswith(":"):
                continue
        
        result = "\n".join(filtered_lines).strip()
        
        # If we couldn't extract a clean description, return original
        if not result or len(result) < 20:
            return prompt
        
        return result
    
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
        
        with open(output_path, "w") as f:
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
    suite_type = SuiteType.HARD if suite.lower() == "hard" else SuiteType.NORMAL
    return loader.load_tasks(suite_type)

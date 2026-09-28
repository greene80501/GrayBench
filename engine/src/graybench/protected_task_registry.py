"""Reviewed, development-only value revisions of pinned QHE tasks."""

from collections.abc import Callable

from graybench.datasets import JudgeTask
from graybench.protected_semantic_judge import ProtectedSemanticTask
from graybench.protected_task2 import task2_value_task
from graybench.protected_task20 import task20_value_task

VALUE_TASKS: dict[str, Callable[[JudgeTask], ProtectedSemanticTask]] = {
    "qiskitHumanEval/2": task2_value_task,
    "qiskitHumanEval/20": task20_value_task,
}


def revised_value_task(source: JudgeTask) -> ProtectedSemanticTask:
    try:
        constructor = VALUE_TASKS[source.public.task_id]
    except KeyError as error:
        raise ValueError("No reviewed protected value revision for this task") from error
    return constructor(source)

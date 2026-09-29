"""Available development-only value revisions of pinned QHE tasks."""

from collections.abc import Callable

from graybench.datasets import JudgeTask
from graybench.protected_semantic_judge import (
    TASK2_ORACLE,
    TASK20_ORACLE,
    TASK20_ORACLE_V2,
    TASK62_ORACLE,
    TASK62_ORACLE_V2,
    ProtectedSemanticTask,
)
from graybench.protected_task2 import task2_value_task
from graybench.protected_task20 import task20_value_task, task20_value_task_v2
from graybench.protected_task62 import task62_value_task, task62_value_task_v2

VALUE_TASKS: dict[str, Callable[[JudgeTask], ProtectedSemanticTask]] = {
    "qiskitHumanEval/2": task2_value_task,
    "qiskitHumanEval/20": task20_value_task_v2,
    "qiskitHumanEval/62": task62_value_task_v2,
}


def revised_value_task(source: JudgeTask, *, oracle: str | None = None) -> ProtectedSemanticTask:
    if oracle is not None:
        historical = {
            ("qiskitHumanEval/2", TASK2_ORACLE): task2_value_task,
            ("qiskitHumanEval/20", TASK20_ORACLE): task20_value_task,
            ("qiskitHumanEval/20", TASK20_ORACLE_V2): task20_value_task_v2,
            ("qiskitHumanEval/62", TASK62_ORACLE): task62_value_task,
            ("qiskitHumanEval/62", TASK62_ORACLE_V2): task62_value_task_v2,
        }
        try:
            return historical[(source.public.task_id, oracle)](source)
        except KeyError as error:
            raise ValueError("No reviewed protected value revision for this oracle") from error
    try:
        constructor = VALUE_TASKS[source.public.task_id]
    except KeyError as error:
        raise ValueError("No reviewed protected value revision for this task") from error
    return constructor(source)

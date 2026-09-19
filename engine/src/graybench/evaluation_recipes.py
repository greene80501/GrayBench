"""Explicit fixed evaluation recipes; no implicit fallback to a different oracle."""

from typing import Literal, get_args

from graybench.file_judge import QpyFileJudge
from graybench.gate_semantics import GateSemanticsJudge
from graybench.oracle_review import BarrierMetricsJudge, CircuitSizeJudge, PauliAnticommutatorJudge
from graybench.upstream import UpstreamJudge

EvaluationRecipe = Literal[
    "upstream",
    "qhe0-size-domain-v1",
    "task82-file-semantic-v1",
    "qhe141-pauli-group-anticommutator-v1",
    "qhe113-barrier-metrics-v1",
    "qhe116-evolution-semantics-v1",
    "qhe120-diagonal-semantics-v1",
]
RECIPES = get_args(EvaluationRecipe)


class RevisionJudge:
    track = "strengthened"

    def __init__(self, recipe, inner, image):
        self.recipe, self.inner, self.image = recipe, inner, image

    def revise(self, task):
        if self.recipe in (
            "qhe141-pauli-group-anticommutator-v1",
            "qhe113-barrier-metrics-v1",
            "qhe116-evolution-semantics-v1",
            "qhe120-diagonal-semantics-v1",
        ):
            return self.inner.revise(task)
        self.inner.configuration(task)  # Reject unsupported families before freezing requests.
        return task

    def configuration(self, task):
        return self.inner.configuration(task)

    def evaluate(self, task, completion):
        return self.inner.evaluate(task, completion)


def recipe_judge(recipe, *, parser_timeout=30, **kwargs):
    kwargs.setdefault("timeout", 120.0)
    if recipe == "upstream":
        return UpstreamJudge(**kwargs)
    if recipe == "qhe0-size-domain-v1":
        inner = CircuitSizeJudge(**kwargs)
    elif recipe == "qhe141-pauli-group-anticommutator-v1":
        inner = PauliAnticommutatorJudge(**kwargs)
    elif recipe == "qhe113-barrier-metrics-v1":
        inner = BarrierMetricsJudge(**kwargs)
    elif recipe in ("qhe116-evolution-semantics-v1", "qhe120-diagonal-semantics-v1"):
        inner = GateSemanticsJudge(recipe, **kwargs)
    elif recipe == "task82-file-semantic-v1":
        inner = QpyFileJudge(parser_timeout=parser_timeout, **kwargs)
    else:
        raise ValueError("Unknown evaluation recipe")
    return RevisionJudge(recipe, inner, kwargs["image"])


def revised_tasks(tasks, judge):
    return (
        tuple(judge.revise(task) for task in tasks) if isinstance(judge, RevisionJudge) else tasks
    )

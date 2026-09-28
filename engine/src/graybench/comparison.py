"""Explicit paired family bootstrap for complete development cohorts."""

import random
import sys
from typing import Literal

from pydantic import Field

from graybench.contracts import Contract, Protocol
from graybench.datasets import JudgeTask
from graybench.identity import identity
from graybench.ledger import StateError
from graybench.protected_semantic_judge import ProtectedSemanticTask
from graybench.provenance import source_manifest
from graybench.providers import adapter


class ComparisonPlan(Contract):
    method: Literal["paired-family-percentile-v1"] = "paired-family-percentile-v1"
    left: Protocol
    right: Protocol
    families: dict[str, str]
    seed: int = Field(ge=0, le=2**32 - 1)
    resamples: int = Field(default=10000, ge=1000, le=100000)
    confidence: float = Field(default=0.95, gt=0, lt=1, allow_inf_nan=False)
    configuration_comparison: str = Field(min_length=1)
    analysis_source: str


def validate_plan(plan):
    if plan.analysis_source != source_manifest()["digest"]:
        raise StateError("Comparison analysis source differs from the frozen plan")
    for field in (
        "track",
        "schema_version",
        "native_cohort_digest",
        "native_suite",
        "native_population",
        "native_exception_policy",
        "protected_cohort_digest",
        "protected_suite",
        "protected_population",
        "protected_excluded",
        "dataset_digest",
        "judge_digest",
        "runtime_digest",
        "generation_code_digest",
        "analysis_digest",
        "repeats",
        "system_prompt",
        "extraction",
        "retry",
        "model_observation_timing",
    ):
        if getattr(plan.left, field) != getattr(plan.right, field):
            raise StateError("Comparison protocols differ in " + field)
    if set(plan.left.task_keys) != set(plan.right.task_keys) or set(plan.families) != set(
        plan.left.task_keys
    ):
        raise StateError("Comparison requires identical frozen task sets")
    if any(not family.strip() for family in plan.families.values()):
        raise StateError("Each task requires an explicit nonempty family")
    if plan.left.analysis_digest != plan.analysis_source:
        raise StateError("Run analysis identity differs from comparison analysis")


def make_plan(
    left, right, tasks, *, seed, configuration_comparison, resamples=10000, confidence=0.95
):
    protected = left.track == "graybench-protected-semantic-v1"
    if any(
        not isinstance(task, ProtectedSemanticTask if protected else JudgeTask) for task in tasks
    ):
        raise StateError("Comparison task type differs from frozen track")
    keyed = {
        f"{public.suite}/{public.task_id}": (task, public)
        for task in tasks
        for public in (task.contract.public if protected else task.public,)
    }
    if len(keyed) != len(tasks) or set(keyed) != set(left.task_keys):
        raise StateError("Task records do not match the comparison cohort")
    datasets = {
        key: (
            {"source": task.contract.source_task_digest, "revised_task": task.digest}
            if protected
            else task.digest
        )
        for key, (task, _) in keyed.items()
    }
    if identity(datasets) != left.dataset_digest:
        raise StateError("Comparison dataset identity mismatch")
    for protocol in (left, right):
        provider = adapter(protocol.model.adapter)
        for key, (_, public) in keyed.items():
            if provider.prepare(
                protocol.model, public, protocol.system_prompt
            ).digest != protocol.request_digests.get(key):
                raise StateError("Comparison request does not match the public task")
    plan = ComparisonPlan(
        left=left,
        right=right,
        families={key: public.family_id for key, (_, public) in keyed.items()},
        seed=seed,
        resamples=resamples,
        confidence=confidence,
        configuration_comparison=configuration_comparison,
        analysis_source=source_manifest()["digest"],
    )
    validate_plan(plan)
    return plan


def family_bootstrap(families, *, seed, resamples, confidence):
    """Resample paired cluster totals; preserve task weighting for unequal cluster sizes."""
    rows = sorted(families, key=lambda row: row["family"])
    samples = sum(row["samples"] for row in rows)
    point = sum(row["left_passes"] - row["right_passes"] for row in rows) / samples
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        chosen = [rows[rng.randrange(len(rows))] for _ in rows]
        draws.append(
            sum(row["left_passes"] - row["right_passes"] for row in chosen)
            / sum(row["samples"] for row in chosen)
        )
    ordered = sorted(draws)

    def quantile(p):
        index = (len(ordered) - 1) * p
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    reason = (
        "fewer_than_two_families"
        if len(rows) < 2
        else ("no_empirical_between_family_variation" if ordered[0] == ordered[-1] else None)
    )
    alpha = (1 - confidence) / 2
    return {
        "left_minus_right": point,
        "interval": None if reason else [quantile(alpha), quantile(1 - alpha)],
        "interval_unavailable_reason": reason,
        "confidence_level": confidence,
        "distribution_digest": identity(draws),
        "family_count": len(rows),
        "rng": "Python 3.12 random.Random/randrange",
        "python": sys.version,
    }


def compare_runs(plan, left_ledger, left_run, right_ledger, right_run, *, tasks):
    validate_plan(plan)
    bound = make_plan(
        plan.left,
        plan.right,
        tasks,
        seed=plan.seed,
        resamples=plan.resamples,
        confidence=plan.confidence,
        configuration_comparison=plan.configuration_comparison,
    )
    if bound.digest != plan.digest:
        raise StateError("Comparison family mapping differs from the bound task records")
    reports = []
    for ledger, run, expected in (
        (left_ledger, left_run, plan.left),
        (right_ledger, right_run, plan.right),
    ):
        ledger.db.execute("BEGIN")
        try:
            if ledger.protocol(run).digest != expected.digest:
                raise StateError("Run does not match its comparison plan")
            report = ledger.summary(run)
            ledger.db.execute("COMMIT")
        except BaseException:
            ledger.db.execute("ROLLBACK")
            raise
        reports.append(report)
    result = {
        "plan_digest": plan.digest,
        "plan": plan.model_dump(mode="json"),
        "runs": reports,
        "publication_eligible": False,
        "preregistration": "not_externally_attested",
        "configuration_equivalence": "not_certified",
        "uncertainty_scope": "paired family resampling conditional on observed outcomes",
        "limitations": [
            "Families are assumed exchangeable, not sampled randomly from all possible tasks.",
            "No independent resampling of stochastic generations or universal model ranking.",
            "Percentile bootstrap coverage can be poor for small or unusual samples.",
            "No multiple-comparison correction or publication admission.",
        ],
    }
    if not all(report["complete"] for report in reports):
        return {**result, "status": "unscored", "comparison": None}
    tasks = [{row["task_key"]: row for row in report["per_task"]} for report in reports]
    families = {}
    for key, family in sorted(plan.families.items()):
        row = families.setdefault(
            family,
            {"family": family, "samples": 0, "left_passes": 0, "right_passes": 0, "tasks": []},
        )
        row["tasks"].append(key)
        row["samples"] += plan.left.repeats
        row["left_passes"] += tasks[0][key]["passes"]
        row["right_passes"] += tasks[1][key]["passes"]
    rows = list(families.values())
    return {
        **result,
        "status": "development_only",
        "families": rows,
        "comparison": family_bootstrap(
            rows, seed=plan.seed, resamples=plan.resamples, confidence=plan.confidence
        ),
    }

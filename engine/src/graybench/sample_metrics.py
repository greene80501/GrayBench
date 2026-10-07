"""Frozen equal-task repeated-sample metrics; no best-answer selection or admission."""

from fractions import Fraction
from math import comb
from typing import Annotated, Literal

from pydantic import Field

from graybench.binary_comparison import probability_record
from graybench.comparison import ComparisonPlan, make_plan, validate_plan, verified_run_report
from graybench.contracts import Contract, Protocol
from graybench.identity import canonical
from graybench.ledger import StateError
from graybench.provenance import source_manifest

MAX_SAMPLES = 1000  # Matches Protocol's frozen repeat bound.
MAX_KS = 100


class SampleMetricsPlan(Contract):
    method: Literal["equal-task-pass-at-k-v1"] = "equal-task-pass-at-k-v1"
    protocol: Protocol
    families: dict[str, str] = Field(min_length=1)
    ks: tuple[Annotated[int, Field(ge=1, le=MAX_SAMPLES)], ...] = Field(
        min_length=1, max_length=MAX_KS
    )
    weighting: Literal["equal_task_v1"] = "equal_task_v1"
    analysis_source: str = Field(pattern=r"^[0-9a-f]{64}$")


def pass_at_k_fraction(n, c, k):
    """Exact fraction of k-subsets containing at least one of c successes."""
    if any(type(value) is not int for value in (n, c, k)):
        raise ValueError("Sample and success counts and k must be strict integers")
    if not 1 <= n <= MAX_SAMPLES or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("Require 1 <= k <= n <= 1000 and 0 <= c <= n")
    return Fraction(1) - Fraction(comb(n - c, k), comb(n, k))


def validate_metrics_plan(plan):
    plan = SampleMetricsPlan.model_validate_json(canonical(plan.model_dump(mode="json")))
    if plan.ks != tuple(sorted(set(plan.ks))) or plan.ks[0] != 1:
        raise StateError("Metrics require unique sorted k values including pass@1")
    if plan.ks[-1] > plan.protocol.repeats:
        raise StateError("Every requested k requires enough frozen samples per task")
    # Reuse the existing complete protocol/source/family identity validation.
    validate_plan(
        ComparisonPlan(
            left=plan.protocol,
            right=plan.protocol,
            families=plan.families,
            seed=0,
            configuration_comparison="Standalone equal-task metric identity binding",
            analysis_source=plan.analysis_source,
        )
    )


def make_metrics_plan(protocol, tasks, *, ks=(1,)):
    ks = tuple(ks)
    if not ks or any(type(k) is not int for k in ks) or len(ks) != len(set(ks)):
        raise StateError("Requested k values must be distinct strict integers")
    bound = make_plan(
        protocol,
        protocol,
        tasks,
        seed=0,
        configuration_comparison="Standalone equal-task metric identity binding",
    )
    plan = SampleMetricsPlan(
        protocol=protocol,
        families=bound.families,
        ks=tuple(sorted(set(ks) | {1})),
        analysis_source=bound.analysis_source,
    )
    validate_metrics_plan(plan)
    return plan


def sample_metrics_report(plan, ledger, run, *, tasks):
    validate_metrics_plan(plan)
    bound = make_metrics_plan(plan.protocol, tasks, ks=plan.ks)
    if bound.digest != plan.digest:
        raise StateError("Metric family mapping differs from bound task records")
    summary = verified_run_report(plan.protocol, ledger, run)
    result = {
        "plan_digest": plan.digest,
        "plan": plan.model_dump(mode="json"),
        "run": summary,
        "analysis_source_manifest": source_manifest(),
        "publication_eligible": False,
        "preregistration": "not_externally_attested",
        "metric_scope": "equal-task mean over all frozen single-answer replicate slots",
        "pass_at_k_scope": "empirical opportunity among k candidates; not pass@1 reliability",
        "limitations": [
            "The combinatorial fraction describes subsets of the retained complete samples.",
            "Future independent k-draw inference requires iid sampling under a fixed policy.",
            "No independence, effective sampling policy or preregistration timing is certified.",
            "No candidate is selected, repaired, or generated again by this analysis.",
            "Pass@k does not measure identifying a correct candidate without a correctness oracle.",
            "Families are descriptive breakdowns, not additional independent observations.",
            "No confidence interval, task admission, provider or runtime qualification is given.",
            "Declared transport retries do not establish first-dispatch provider behavior.",
        ],
    }
    if not summary["complete"]:
        return {
            **result,
            "status": "unscored",
            "metrics": None,
            "per_task_metrics": None,
            "family_metrics": None,
        }
    keyed = {row["task_key"]: row for row in summary["per_task"]}
    exact = {
        key: {
            f"pass@{k}": pass_at_k_fraction(plan.protocol.repeats, keyed[key]["passes"], k)
            for k in plan.ks
        }
        for key in sorted(plan.families)
    }

    def average(keys):
        return {
            f"pass@{k}": probability_record(
                sum((exact[key][f"pass@{k}"] for key in keys), Fraction(0)) / len(keys)
            )
            for k in plan.ks
        }

    families = {}
    for key, family in sorted(plan.families.items()):
        families.setdefault(family, []).append(key)
    return {
        **result,
        "status": "development_only",
        "task_count": len(exact),
        "metrics": average(tuple(exact)),
        "per_task_metrics": [
            {
                "task_key": key,
                "family": plan.families[key],
                "samples": plan.protocol.repeats,
                "passes": keyed[key]["passes"],
                "metrics": {k: probability_record(value) for k, value in scores.items()},
            }
            for key, scores in exact.items()
        ],
        "family_metrics": [
            {"family": family, "task_count": len(keys), "tasks": keys, "metrics": average(keys)}
            for family, keys in sorted(families.items())
        ],
    }


def verify_sample_metrics(report, plan, ledger, run, *, tasks):
    replay = sample_metrics_report(plan, ledger, run, tasks=tasks)
    if canonical(report) != canonical(replay):
        raise StateError("Saved sample metrics differ from their complete ledger replay")
    return {
        "verified": True,
        "plan_digest": plan.digest,
        "status": replay["status"],
        "publication_eligible": False,
    }

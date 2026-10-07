"""Exact McNemar and complete planned Holm studies, conditional on assumptions."""

import json
from fractions import Fraction
from typing import Literal

from pydantic import Field

from graybench.comparison import make_plan, validate_plan, verified_comparison_reports
from graybench.contracts import Contract, Protocol
from graybench.identity import canonical
from graybench.ledger import StateError
from graybench.provenance import source_manifest

MAX_PAIRS = 10000


def load_binary_json(payload):
    """Do not silently replace named contrasts or report fields with duplicate keys."""

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise StateError("Duplicate JSON keys are not permitted in frozen analysis")
            result[key] = value
        return result

    value = json.loads(payload, object_pairs_hook=unique)
    canonical(value)  # reject non-finite JSON extensions
    return value


class BinaryComparisonPlan(Contract):
    method: Literal["paired-binary-exact-mcnemar-v1"] = "paired-binary-exact-mcnemar-v1"
    left: Protocol
    right: Protocol
    families: dict[str, str] = Field(min_length=1, max_length=MAX_PAIRS)
    configuration_comparison: str = Field(min_length=1)
    independence_basis: str = Field(min_length=1)
    analysis_source: str = Field(pattern=r"^[0-9a-f]{64}$")


class BinaryContrast(Contract):
    contrast_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
    plan: BinaryComparisonPlan


class BinaryStudyPlan(Contract):
    method: Literal["planned-exact-mcnemar-holm-v1"] = "planned-exact-mcnemar-holm-v1"
    contrasts: tuple[BinaryContrast, ...] = Field(min_length=1, max_length=100)
    alpha: float = Field(default=0.05, gt=0, lt=1, allow_inf_nan=False)
    purpose: str = Field(min_length=1)
    analysis_source: str = Field(pattern=r"^[0-9a-f]{64}$")


class BinaryStudyRun(Contract):
    left_ledger: str = Field(min_length=1)
    left_run: str = Field(min_length=1)
    right_ledger: str = Field(min_length=1)
    right_run: str = Field(min_length=1)


def exact_mcnemar(left_only, right_only):
    """Two-sided conditional binomial tail, with no floating point decisions."""
    if any(type(count) is not int or count < 0 for count in (left_only, right_only)):
        raise ValueError("Discordance counts must be nonnegative integers")
    n = left_only + right_only
    if n > MAX_PAIRS:
        raise ValueError("Discordance counts exceed the declared 10000-pair analysis bound")
    term = total = 1
    for k in range(1, min(left_only, right_only) + 1):
        term = term * (n - k + 1) // k
        total += term
    return min(Fraction(1), Fraction(2 * total, 1 << n))


def probability_record(probability):
    if type(probability) is not Fraction or not 0 <= probability <= 1:
        raise ValueError("An exact probability Fraction is required")
    approximate = float(probability)
    underflow = probability > 0 and approximate == 0
    return {
        "numerator_hex": hex(probability.numerator),
        "denominator_hex": hex(probability.denominator),
        "float_value": None if underflow else approximate,
        "float_underflow": underflow,
    }


def holm_adjust(probabilities):
    if not probabilities or len(probabilities) > 100:
        raise ValueError("Holm requires one to 100 complete planned contrasts")
    for key, probability in probabilities.items():
        if type(key) is not str or not key.strip():
            raise ValueError("Named contrasts are required")
        probability_record(probability)
    ranked = sorted(probabilities, key=lambda key: (probabilities[key], key))
    previous = Fraction(0)
    result = {}
    for rank, key in enumerate(ranked):
        previous = max(previous, min(Fraction(1), (len(ranked) - rank) * probabilities[key]))
        result[key] = previous
    return {key: result[key] for key in probabilities}


def validate_binary_plan(plan):
    # Revalidate frozen objects too: model_copy deliberately bypasses Pydantic validation.
    plan = BinaryComparisonPlan.model_validate_json(canonical(plan.model_dump(mode="json")))
    validate_plan(plan)
    if plan.left.repeats != 1:
        raise StateError("Exact binary analysis requires one sample per task")
    if len(set(plan.families.values())) != len(plan.families):
        raise StateError("Exact binary analysis requires one task per family")
    if not plan.independence_basis.strip() or not plan.configuration_comparison.strip():
        raise StateError("Explicit independence and configuration declarations are required")


def make_binary_plan(left, right, tasks, *, configuration_comparison, independence_basis):
    bound = make_plan(
        left,
        right,
        tasks,
        seed=0,
        resamples=1000,
        configuration_comparison=configuration_comparison,
    )
    plan = BinaryComparisonPlan(
        left=bound.left,
        right=bound.right,
        families=bound.families,
        configuration_comparison=configuration_comparison,
        independence_basis=independence_basis,
        analysis_source=bound.analysis_source,
    )
    validate_binary_plan(plan)
    return plan


def validate_binary_study(plan):
    plan = BinaryStudyPlan.model_validate_json(canonical(plan.model_dump(mode="json")))
    if not plan.purpose.strip():
        raise StateError("An explicit study purpose is required")
    if plan.analysis_source != source_manifest()["digest"]:
        raise StateError("Study analysis source differs from the frozen plan")
    ids, pairs = set(), set()
    for contrast in plan.contrasts:
        validate_binary_plan(contrast.plan)
        pair = tuple(sorted((contrast.plan.left.digest, contrast.plan.right.digest)))
        if contrast.contrast_id in ids or pair in pairs:
            raise StateError("Study requires unique contrast IDs and protocol pairs")
        ids.add(contrast.contrast_id)
        pairs.add(pair)


def make_binary_study(contrasts, *, purpose, alpha=0.05):
    plan = BinaryStudyPlan(
        contrasts=tuple(contrasts),
        purpose=purpose,
        alpha=alpha,
        analysis_source=source_manifest()["digest"],
    )
    validate_binary_study(plan)
    return plan


def compare_binary_runs(plan, left_ledger, left_run, right_ledger, right_run, *, tasks):
    validate_binary_plan(plan)
    bound = make_binary_plan(
        plan.left,
        plan.right,
        tasks,
        configuration_comparison=plan.configuration_comparison,
        independence_basis=plan.independence_basis,
    )
    if bound.digest != plan.digest:
        raise StateError("Binary comparison family mapping differs from bound task records")
    reports = verified_comparison_reports(plan, left_ledger, left_run, right_ledger, right_run)
    result = {
        "plan_digest": plan.digest,
        "plan": plan.model_dump(mode="json"),
        "runs": reports,
        "publication_eligible": False,
        "preregistration": "not_externally_attested",
        "configuration_equivalence": "not_certified",
        "independence": "operator-declared; not established by distinct family identifiers",
        "limitations": [
            "Conditional inference requires independent paired observations across families.",
            "Under the null, conditional discordant directions must be independent Bernoulli(1/2).",
            "Equal aggregate finite-cohort rates alone do not establish that conditional null.",
            "One sample per family does not measure generation variability or universal accuracy.",
            "Effect size is descriptive; the p-value is not the probability a model is superior.",
            "Repeated generations or related normal/hard tasks require cluster-aware analysis.",
            "No task admission, provider attestation or publication eligibility is supplied.",
        ],
    }
    if not all(report["complete"] for report in reports):
        return {**result, "status": "unscored", "comparison": None, "pairs": None}
    keyed = [{row["task_key"]: row for row in report["per_task"]} for report in reports]
    pairs = []
    counts = {"both_pass": 0, "left_only": 0, "right_only": 0, "both_not_pass": 0}
    for key, family in sorted(plan.families.items()):
        left, right = (bool(rows[key]["passes"]) for rows in keyed)
        category = (
            "both_pass"
            if left and right
            else "left_only"
            if left
            else "right_only"
            if right
            else "both_not_pass"
        )
        counts[category] += 1
        pairs.append({"task_key": key, "family": family, "left_pass": left, "right_pass": right})
    p = exact_mcnemar(counts["left_only"], counts["right_only"])
    return {
        **result,
        "status": "development_only",
        "pairs": pairs,
        "comparison": {
            "counts": counts,
            "pair_count": len(pairs),
            "left_minus_right": (counts["left_only"] - counts["right_only"]) / len(pairs),
            "null_hypothesis": "equal marginal pass probabilities",
            "conditional_null": (
                "Under the paired-population null and conditional on discordance, "
                "directions are independent Bernoulli(1/2)."
            ),
            "alternative": "two-sided",
            "exact_p": probability_record(p),
            "multiplicity": "uncorrected; use the full planned study for Holm adjustment",
        },
    }


def compare_binary_study(plan, inputs, *, tasks):
    validate_binary_study(plan)
    expected = {contrast.contrast_id for contrast in plan.contrasts}
    if set(inputs) != expected or set(tasks) != expected:
        raise StateError("Study requires every planned contrast and no extras")
    reports = {
        contrast.contrast_id: compare_binary_runs(
            contrast.plan, *inputs[contrast.contrast_id], tasks=tasks[contrast.contrast_id]
        )
        for contrast in plan.contrasts
    }
    result = {
        "plan_digest": plan.digest,
        "plan": plan.model_dump(mode="json"),
        "contrasts": reports,
        "publication_eligible": False,
        "preregistration": "not_externally_attested",
        "familywise_alpha": plan.alpha,
        "threshold_fraction": probability_record(Fraction(str(plan.alpha))),
    }
    if any(report["status"] != "development_only" for report in reports.values()):
        return {**result, "status": "unscored", "holm": None}
    probabilities = {
        key: exact_mcnemar(
            report["comparison"]["counts"]["left_only"],
            report["comparison"]["counts"]["right_only"],
        )
        for key, report in reports.items()
    }
    adjusted = holm_adjust(probabilities)
    threshold = Fraction(str(plan.alpha))
    return {
        **result,
        "status": "development_only",
        "holm": {
            key: {
                "adjusted_p": probability_record(value),
                "reject_equal_marginals": value <= threshold,
            }
            for key, value in adjusted.items()
        },
    }


def verify_binary_study(report, plan, inputs, *, tasks):
    """Replay all bound ledgers and math; this is consistency, not author attestation."""
    replay = compare_binary_study(plan, inputs, tasks=tasks)
    if canonical(report) != canonical(replay):
        raise StateError("Saved binary study differs from its complete ledger replay")
    return {
        "verified": True,
        "plan_digest": plan.digest,
        "status": replay["status"],
        "publication_eligible": False,
    }

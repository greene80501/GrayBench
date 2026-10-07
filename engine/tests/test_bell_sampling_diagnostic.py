import importlib.util
import itertools
import json
import os
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "docs/reliability-evidence/bell_sampling_diagnostic.py"
)
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")


def diagnostic():
    assert SCRIPT.is_file(), "Missing source-bound Bell sampling diagnostic"
    spec = importlib.util.spec_from_file_location("bell_sampling_diagnostic", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_task1_exact_acceptance_matches_exhaustive_ordered_shots():
    module = diagnostic()
    for shots in range(1, 11):
        accepted = 0
        for row in itertools.product(("00", "11"), repeat=shots):
            counts = Counter(row)
            accepted += set(counts) == {"00", "11"} and 0.4 < counts["00"] / shots < 0.6
        expected = Fraction(accepted, 2**shots)
        assert module.task1_acceptance(shots) == expected
        assert module.recurrence_acceptance(shots) == expected


@pytest.mark.parametrize(
    "shots,want",
    [(1, 0), (2, Fraction(1, 2)), (3, 0), (4, Fraction(3, 8)), (5, 0), (10, Fraction(63, 256))],
)
def test_task1_strict_boundaries_do_not_become_inclusive(shots, want):
    assert diagnostic().task1_acceptance(shots) == want


@pytest.mark.parametrize("shots", [True, 0, -1, 1.5, 2049])
def test_invalid_shot_domain_is_not_coerced(shots):
    with pytest.raises(ValueError, match="integer|shots"):
        diagnostic().task1_acceptance(shots)


def test_task14_missing_support_probability_includes_both_tails():
    module = diagnostic()
    assert module.missing_support_probability(1) == 1
    assert module.missing_support_probability(2) == Fraction(1, 2)
    assert module.missing_support_probability(100) == Fraction(1, 2**99)


def test_noise_event_probability_does_not_assume_a_noise_model():
    module = diagnostic()
    assert module.no_outside_event_probability(4, Fraction(0)) == 1
    assert module.no_outside_event_probability(4, Fraction(1)) == 0
    assert module.no_outside_event_probability(4, Fraction(1, 2)) == Fraction(1, 16)
    for noise in (Fraction(-1, 2), Fraction(3, 2), 0.1, True):
        with pytest.raises(ValueError, match="rational|probability"):
            module.no_outside_event_probability(4, noise)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE")
def test_exact_checks_expose_invalid_counts_and_undisclosed_constraints():
    module = diagnostic()
    tasks = module.tasks_at(Path(CACHE))
    rows = module.probe(tasks)
    results = {(row["suite"], row["task_id"], row["case_id"]): row["judgment"] for row in rows}
    for suite in ("normal", "hard"):
        for case in ("negative_counts", "fractional_counts", "two_shot_balance"):
            assert results[suite, 1, case]["outcome"] == "pass"
        assert results[suite, 1, "zero_total"]["exception"] == "ZeroDivisionError"
        for case in ("two_shots", "99_shots", "101_shots"):
            assert results[suite, 14, case]["outcome"] == "pass"
        assert results[suite, 14, "100_identical_shots"]["outcome"] == "fail"
        assert results[suite, 15, "ideal_bell_counts"]["outcome"] == "fail"
        assert results[suite, 15, "psi_bell_counts"]["exception"] == "KeyError"
        for case in ("negative_error_count", "fractional_counts", "invalid_bitstring"):
            assert results[suite, 15, case]["outcome"] == "pass"
        assert results[suite, 31, "floating_counts"]["outcome"] == "pass"
        assert results[suite, 31, "other_total"]["outcome"] == "fail"
        assert results[suite, 31, "psi_bell_counts"]["outcome"] == "fail"
    changed = list(tasks)
    changed[0] = changed[0].model_copy(update={"upstream_test": "raise RuntimeError"})
    with pytest.raises(ValueError, match="exact pinned"):
        module.probe(changed)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE")
def test_analytic_probabilities_match_every_exact_check_in_bounded_counts_domain():
    module = diagnostic()
    tasks = module.tasks_at(Path(CACHE))
    check = module.exact_check(tasks[0])
    for shots in (*range(1, 129), 1000, 1024):
        # Each equally likely ordered sequence is counted by an independent
        # Pascal-row construction, while acceptance comes from the pinned check.
        weights = [1]
        for _ in range(shots):
            weights = [1, *[a + b for a, b in zip(weights, weights[1:], strict=False)], 1]
        accepted = sum(
            weight
            for count, weight in enumerate(weights)
            if module.observe(
                check,
                {key: value for key, value in (("00", count), ("11", shots - count)) if value},
            )["outcome"]
            == "pass"
        )
        assert module.task1_acceptance(shots) == Fraction(accepted, 2**shots)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE")
def test_plan_and_replay_fail_closed_without_sampler_attestation():
    module = diagnostic()
    cache = Path(CACHE)
    declared = module.plan(cache)
    report = module.build(cache, declared)
    assert module.verify(report, declared, cache)
    assert report["isolated_sampler_executed"] is False
    assert report["publication_eligible"] is False
    assert report["model_generations"] == 0
    assert report["task14_all_identical_100_shots"] == {"numerator": 1, "denominator": 2**99}
    with pytest.raises(ValueError, match="predeclared plan"):
        module.build(cache, {**declared, "shot_counts": [1000]})
    with pytest.raises(ValueError, match="exact recreation"):
        module.verify({**report, "controls": []}, declared, cache)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE")
def test_cli_preserves_existing_evidence_and_checks_exact_replay(tmp_path):
    path = tmp_path / "report.json"
    args = [sys.executable, str(SCRIPT), CACHE, str(path)]
    first = subprocess.run(args, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    original = path.read_bytes(), path.with_name("plan.json").read_bytes()
    duplicate = subprocess.run(args, capture_output=True, text=True)
    assert duplicate.returncode != 0
    assert original == (path.read_bytes(), path.with_name("plan.json").read_bytes())
    assert subprocess.run([*args, "--check"], capture_output=True).returncode == 0
    report = json.loads(path.read_bytes())
    report["controls"] = []
    path.write_text(json.dumps(report), encoding="utf-8")
    assert subprocess.run([*args, "--check"], capture_output=True).returncode != 0

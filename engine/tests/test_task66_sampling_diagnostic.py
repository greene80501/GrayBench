import importlib.util
import itertools
import os
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pytest

from graybench.datasets import load_suite

SCRIPT = (
    Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task66_sampling_diagnostic.py"
)


def diagnostic():
    assert SCRIPT.is_file(), "Missing source-bound Task66 sampling diagnostic"
    spec = importlib.util.spec_from_file_location("task66_sampling_diagnostic", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exact_multinomial_acceptance_matches_exhaustive_ordered_shots():
    module = diagnostic()
    for shots in range(8):
        sequences = [Counter(row) for row in itertools.product(range(3), repeat=shots)]
        for lower in range(shots + 1):
            for upper in range(lower, shots + 1):
                accepted = sum(
                    all(lower <= row.get(key, 0) <= upper for key in range(3)) for row in sequences
                )
                assert module.acceptance_probability(shots, lower, upper) == Fraction(
                    accepted, 3**shots
                )


@pytest.mark.parametrize(
    "args", [(True, 0, 1), (3, False, 2), (3, 0, 2.0), (-1, 0, 0), (3, 2, 1), (3, 0, 4)]
)
def test_probability_calibration_rejects_invalid_domains(args):
    with pytest.raises(ValueError, match="strict integers|count bounds"):
        diagnostic().acceptance_probability(*args)


def test_task66_exact_ideal_failure_probability_is_nonzero():
    module = diagnostic()
    probability = module.acceptance_probability(1024, 300, 400)
    assert probability == module.factorial_acceptance_probability(1024, 300, 400)
    assert Fraction(98, 100) < probability < Fraction(1)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Needs pinned QHE")
def test_exact_assertion_slices_distinguish_sampling_from_state_correctness():
    module = diagnostic()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    tasks = tuple(load_suite(suite, cache)[66] for suite in ("normal", "hard"))
    rows = module.probe(*tasks)
    assert len(rows) == 9
    for row in rows:
        assert row["sdk_probability_error"] < 1e-14
        assert row["sdk_fidelity_error"] < 1e-14
        assert row["counts"]["balanced"]["normal"]["outcome"] == "pass"
        assert row["counts"]["balanced"]["hard"]["outcome"] == "pass"
        assert row["counts"]["inclusive_boundary"]["normal"]["outcome"] == "pass"
        for name in ("lower_tail", "upper_tail", "incorrect_total"):
            assert row["counts"][name]["normal"]["outcome"] == "fail"
            assert row["counts"][name]["hard"]["outcome"] == "fail"
        assert row["counts"]["outside_support"]["normal"]["exception"] == "AttributeError"
        assert row["counts"]["outside_support"]["hard"]["exception"] == "AttributeError"
    assert [row["symmetric_w_up_to_global_phase"] for row in rows] == [True] * 4 + [False] * 5
    assert rows[-1]["expected_symmetric_w_fidelity"] == {"numerator": 0, "denominator": 1}
    assert module.probe(*tasks) == rows
    with pytest.raises(ValueError, match="exact pinned Task66"):
        module.probe(tasks[0].model_copy(update={"upstream_test": "raise RuntimeError"}), tasks[1])


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Needs pinned QHE")
def test_predeclared_plan_and_exact_recreation_bind_source_and_records(tmp_path):
    module = diagnostic()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    plan = module.plan(cache)
    assert plan["fixture_count"] == 9
    assert plan["assertion_trials"] == 9 * 6 * 2
    report = module.build(cache, plan)
    assert report["publication_eligible"] is False
    assert report["isolated_sampler_executed"] is False
    assert report["sampling_assumption"] == "1024 independent ideal equal-probability shots"
    assert module.verify(report, plan, cache)
    changed = {**plan, "assertion_trials": 1}
    with pytest.raises(ValueError, match="predeclared plan"):
        module.build(cache, changed)
    with pytest.raises(ValueError, match="exact recreation"):
        module.verify({**report, "controls": []}, plan, cache)

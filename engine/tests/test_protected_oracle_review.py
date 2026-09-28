"""The authored control suite has explicit positives and semantically wrong mutants."""

import pytest
from test_native_cohort import cache as _synthetic_cache

from graybench.datasets import load_suite
from graybench.protected_oracle_review import protected_probes, run_protected_review


@pytest.fixture
def cache(tmp_path, monkeypatch):
    return _synthetic_cache.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.parametrize("task_id,entry", [("2", "bell_amplitudes"), ("20", "ghz_amplitudes")])
def test_authored_value_controls_have_independent_positives_and_valid_wrong_mutants(
    cache, task_id, entry
):
    source = next(
        task
        for task in load_suite("normal", cache)
        if task.public.task_id == f"qiskitHumanEval/{task_id}"
    )
    controls = protected_probes(source)
    assert len(controls) == len({control.name for control in controls}) == 6
    assert [control.expectation for control in controls] == [
        "pass",
        "pass",
        "pass",
        "fail",
        "fail",
        "fail",
    ]
    assert all(f"def {entry}(" in control.completion for control in controls)
    assert all(control.rationale for control in controls)


def test_protected_control_runner_rejects_duplicate_selection_before_creating_log(cache, tmp_path):
    output = tmp_path / "review.jsonl"
    with pytest.raises(ValueError, match="duplicate"):
        run_protected_review(
            cache,
            output,
            suite="normal",
            image="sha256:" + "a" * 64,
            task_ids=("qiskitHumanEval/2", "qiskitHumanEval/2"),
        )
    assert not output.exists()

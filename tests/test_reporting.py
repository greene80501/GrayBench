import json

import pytest

from graybench.metrics import wilson_interval
from graybench.storage import ResultStorage
from graybench.preflight import fingerprint, verify_report, environment, evaluator_fingerprint
from graybench.dataset import Dataset
from test_evaluation import example


def attempt(db, run_id, task_id="test/0", passed=True, cost=0.01):
    db.record_attempt(
        run_id=run_id,
        task_id=task_id,
        prompt="prompt",
        completion="completion",
        extracted_code="",
        extraction_success=True,
        outcome="pass" if passed else "fail_test",
        passed=passed,
        error_type=None,
        error_message=None,
        stdout="",
        stderr="",
        generation_latency_ms=1,
        execution_time_ms=1,
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        cost_usd=cost,
        raw_response={},
    )


def test_incomplete_run_cannot_be_reported_complete(tmp_path):
    db = ResultStorage(tmp_path / "results.db")
    run = db.create_run("normal", "openai", "test", manifest={"task_ids": ["test/0", "test/1"]})
    attempt(db, run)
    with pytest.raises(ValueError, match="Incomplete"):
        db.complete_run(run)
    assert db.get_run(run)["status"] == "running"


def test_unknown_cost_stays_unknown(tmp_path):
    db = ResultStorage(tmp_path / "results.db")
    run = db.create_run("normal", "openai", "test")
    attempt(db, run, cost=None)
    db.complete_run(run)
    assert db.get_scores(run)["total_cost_usd"] is None
    assert (
        db.get_leaderboard() == []
    )  # No validated protocol: never mixed into the new leaderboard.


def test_duplicates_cannot_inflate_pass_rate(tmp_path):
    db = ResultStorage(tmp_path / "results.db")
    run = db.create_run("normal", "openai", "test")
    attempt(db, run)
    attempt(db, run)
    with pytest.raises(ValueError, match="duplicate"):
        db.complete_run(run)


def test_wilson_small_sample_remains_uncertain():
    low, high = wilson_interval(1, 1)
    assert 0.20 < low < 0.21 and high == 1
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


def test_changed_reference_invalidates_preflight():
    d = Dataset([example()], "normal")
    report = {
        "dataset_hash": d.dataset_hash,
        "suite": "normal",
        "environment": environment(),
        "evaluator": evaluator_fingerprint(),
        "results": [{"task_id": "test/0", "passed": True}],
        "task_ids": ["test/0"],
    }
    report["fingerprint"] = fingerprint(report)
    assert verify_report(report, d) == ["test/0"]
    report["task_ids"].append("test/1")
    with pytest.raises(ValueError, match="fingerprint"):
        verify_report(report, d)


def test_api_failures_do_not_become_a_zero_percent_model_score(tmp_path):
    db = ResultStorage(tmp_path / "results.db")
    run = db.create_run("normal", "google", "test")
    attempt(db, run, passed=False, cost=None)
    with db._connect() as conn:
        conn.execute("UPDATE attempts SET outcome='api_error' WHERE run_id=?", (run,))
    with pytest.raises(ValueError, match="Operational API failures"):
        db.complete_run(run)
    assert db.get_scores(run) is None

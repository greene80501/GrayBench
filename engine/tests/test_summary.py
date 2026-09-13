from pathlib import Path

import pytest

from graybench.contracts import Generation
from graybench.ledger import Ledger, StateError
from graybench.providers import Ollama


def fill(ledger, protocol, task, outcomes):
    run = ledger.create_run(protocol)
    samples = ledger.samples(run)
    for sample, outcome in zip(samples, outcomes, strict=True):
        attempt = ledger.begin_attempt(sample["id"], Ollama().prepare(protocol.model, task, None))
        ledger.finish_attempt(
            attempt,
            "returned",
            {},
            200,
            Generation(
                text="answer",
                returned_model=protocol.model.model,
                response_id=None,
                finish_reason="stop",
                usage={},
            ),
        )
        if outcome is not None:
            ledger.judge(sample["id"], protocol.judge_digest, outcome, {})
    return run


def test_balanced_repeated_single_attempt_estimator_is_development_only(ledger, protocol, task):
    protocol = protocol.model_copy(update={"repeats": 3})
    run = fill(ledger, protocol, task, ["pass", "fail", "timeout"])
    report = ledger.summary(run)
    assert report["planned_samples"] == 3
    assert report["pass_at_1"] == pytest.approx(1 / 3)
    assert report["outcome_counts"]["timeout"] == 1
    assert report["per_task"][0]["passes"] == 1
    assert report["score_status"] == "development_only"
    assert report["publication_eligible"] is False
    assert report["publication_blockers"]
    assert report["score_blockers"] == []


def test_different_analysis_engine_cannot_recompute_a_frozen_score(ledger, protocol, task):
    protocol = protocol.model_copy(update={"analysis_digest": "0" * 64})
    run = fill(ledger, protocol, task, ["pass"])
    report = ledger.summary(run)
    assert report["passes"] == 1
    assert report["pass_at_1"] is None
    assert report["score_blockers"] == ["analysis_source_mismatch"]
    assert report["analysis_identity"]["matched"] is False


def test_missing_schedule_row_cannot_shrink_the_denominator(ledger, protocol, task):
    protocol = protocol.model_copy(update={"repeats": 2})
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]
    ledger.db.execute("DROP TRIGGER immutable_samples_DELETE")
    ledger.db.execute("DELETE FROM samples WHERE id=?", (sample["id"],))
    report = ledger.summary(run)
    assert report["planned_samples"] == 2
    assert report["observed_samples"] == 1
    assert report["cohort"]["missing"] == [[sample["task_key"], sample["replicate"]]]
    assert "frozen_cohort_mismatch" in report["score_blockers"]
    assert report["pass_at_1"] is None


def test_unexpected_row_is_not_silently_included(ledger, protocol, task):
    run = fill(ledger, protocol, task, ["pass"])
    ledger.db.execute("INSERT INTO samples VALUES (?,?,?,?)", ("extra", run, "extra-task", 0))
    report = ledger.summary(run)
    assert report["planned_samples"] == 1
    assert report["cohort"]["unexpected"] == [["extra-task", 0]]
    assert report["score_status"] == "unscored"


def test_unscored_outcomes_are_explicit_not_merged_into_failures(ledger, protocol, task):
    protocol = protocol.model_copy(update={"repeats": 4})
    run = fill(ledger, protocol, task, ["pass", "unsupported", "infrastructure_error", None])
    report = ledger.summary(run)
    assert report["pass_at_1"] is None
    assert report["outcome_counts"]["fail"] == 0
    assert set(report["score_blockers"]) == {
        "unsupported",
        "infrastructure_error",
        "unjudged_samples",
    }
    assert report["outcome_counts"]["unjudged"] == 1


def test_summary_rejects_corrupt_evidence_and_releases_snapshot(ledger, protocol, task):
    run = fill(ledger, protocol, task, ["pass"])
    ledger.db.execute("DROP TRIGGER immutable_blobs_UPDATE")
    ledger.db.execute(
        "UPDATE blobs SET content=? WHERE digest=(SELECT manifest FROM runs WHERE id=?)",
        (b"{}", run),
    )
    with pytest.raises(StateError, match="digest mismatch"):
        ledger.summary(run)
    assert not ledger.db.in_transaction


def test_summary_uses_one_snapshot_during_a_concurrent_judgment(
    ledger, protocol, task, monkeypatch
):
    run = fill(ledger, protocol, task, [None])
    sample = ledger.samples(run)[0]["id"]
    path = ledger.db.execute("PRAGMA database_list").fetchone()[2]
    writer = Ledger(Path(path))
    verify = ledger.verify
    before = verify()

    def concurrent_write():
        result = verify()
        writer.judge(sample, protocol.judge_digest, "pass", {})
        return result

    monkeypatch.setattr(ledger, "verify", concurrent_write)
    try:
        report = ledger.summary(run)
    finally:
        writer.close()
    assert report["pass_at_1"] is None
    assert report["ledger_integrity"]["chain_head"] == before["chain_head"]
    monkeypatch.setattr(ledger, "verify", verify)
    assert ledger.summary(run)["pass_at_1"] == 1

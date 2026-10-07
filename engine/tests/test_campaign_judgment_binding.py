"""A model score must agree with the bound trusted verdict, not merely row hashes."""

import copy
import hashlib
import json

import pytest
from test_evaluation_campaign import configured, saved_answer
from test_ledger_evidence import events, rechain

from graybench.campaign_setup import build_setup
from graybench.contracts import Protocol
from graybench.evaluation_campaign import JudgmentRunner, cohort_identities
from graybench.identity import canonical, identity
from graybench.judge import Judgment
from graybench.judgment_evidence import validate_judgment_result
from graybench.ledger import StateError
from graybench.upstream_evidence import capture_judgment


def captured(judge, task, outcome="pass", completion="def answer(x): return x+1"):
    _, manifest = judge.configuration(task)
    message, artifact = capture_judgment(
        canonical({"kind": "judgment", "outcome": outcome, "evidence": {"calls": 1}}) + b"\n",
        limit=manifest["output_limit"],
    )
    return {
        "manifest": manifest,
        "completion_sha256": hashlib.sha256(completion.encode()).hexdigest(),
        "calls": 1,
        "termination_source": "trusted_judgment",
        "trusted_judgment": message,
        "trusted_judgment_artifact": artifact,
    }


def bound_result(ledger, run, task, judge, outcome="pass"):
    sample = ledger.samples(run)[0]["id"]
    content = ledger.db.execute(
        "SELECT content FROM generations WHERE sample_id=?", (sample,)
    ).fetchone()[0]
    evidence = {
        "cohort": cohort_identities((task,), judge),
        "generation_digest": content,
        "task_judge_digest": identity(judge.configuration(task)[1]),
        "judgment": captured(judge, task, outcome),
    }
    return sample, evidence


def test_live_runner_does_not_score_pass_that_disagrees_with_trusted_fail(
    ledger, protocol, task, monkeypatch
):
    protocol, task, judge = configured(protocol, task)
    run = saved_answer(ledger, protocol, task)
    bad = Judgment("pass", identity(judge.configuration(task)[1]), captured(judge, task, "fail"))
    monkeypatch.setattr(judge, "evaluate", lambda *_: bad)
    result = JudgmentRunner(ledger, run, (task,), judge).step()
    assert result["outcome"] == "infrastructure_error"
    report = ledger.summary(run)
    assert report["pass_at_1"] is None
    assert report["judgment_evidence_binding"] == {"bound": 1, "legacy_unbound": 0}
    raw = ledger.blob(ledger.db.execute("SELECT evidence FROM judgments").fetchone()[0])
    assert raw["rejected_judgment"]["outcome"] == "pass"
    assert raw["rejected_judgment"]["evidence"]["trusted_judgment"]["outcome"] == "fail"


def test_direct_recording_rejects_contradictory_trusted_capture(ledger, protocol, task):
    protocol, task, judge = configured(protocol, task)
    run = saved_answer(ledger, protocol, task)
    sample, evidence = bound_result(ledger, run, task, judge, "fail")
    with pytest.raises(StateError, match="trusted judgment"):
        ledger.judge(sample, protocol.judge_digest, "pass", evidence)
    assert not ledger.db.execute("SELECT 1 FROM judgments").fetchone()


def test_rehashed_report_cannot_turn_captured_fail_into_pass(ledger, protocol, task):
    protocol, task, judge = configured(protocol, task)
    run = saved_answer(ledger, protocol, task)
    sample, evidence = bound_result(ledger, run, task, judge, "fail")
    ledger.judge(sample, protocol.judge_digest, "fail", evidence)
    assert ledger.summary(run)["pass_at_1"] == 0
    ledger.db.execute("DROP TRIGGER immutable_judgments_UPDATE")
    ledger.db.execute("UPDATE judgments SET outcome='pass' WHERE sample_id=?", (sample,))
    records = events(ledger)
    for event in records:
        if event["kind"] == "judgment_recorded":
            event["outcome"] = "pass"
            event["records"]["judgments"][0]["outcome"] = "pass"
    rechain(ledger, records)
    with pytest.raises(StateError, match="trusted judgment"):
        ledger.summary(run)


@pytest.mark.parametrize("change", ["generation", "task_judge", "manifest", "cohort"])
def test_recognized_campaign_evidence_rejects_mismatched_bindings(ledger, protocol, task, change):
    protocol, task, judge = configured(protocol, task)
    run = saved_answer(ledger, protocol, task)
    sample, original = bound_result(ledger, run, task, judge)
    evidence = copy.deepcopy(original)
    if change == "generation":
        evidence["generation_digest"] = "f" * 64
    elif change == "task_judge":
        evidence["task_judge_digest"] = "f" * 64
    elif change == "manifest":
        evidence["judgment"]["manifest"].pop("trusted_judgment_capture")
    else:
        evidence["cohort"]["tasks"][task.public.suite + "/" + task.public.task_id] = "f" * 64
    with pytest.raises(StateError):
        ledger.judge(sample, protocol.judge_digest, "pass", evidence)


def test_new_plans_require_bound_judgments_and_legacy_serialization_is_preserved(
    model, protocol, task
):
    _, task, judge = configured(protocol, task)
    setup = build_setup("bound", model, (task,), judge.image, protocol_version="3.1")
    assert setup.protocol.judgment_evidence_policy == "cohort-bound-v1"
    restored = Protocol.model_validate_json(setup.protocol.model_dump_json())
    assert restored == setup.protocol
    old = setup.protocol.model_dump(mode="json")
    old.pop("judgment_evidence_policy")
    legacy = Protocol.model_validate_json(canonical(old))
    assert legacy.judgment_evidence_policy is None
    assert legacy.digest == identity(old)


def test_declared_policy_rejects_omission_of_all_binding_fields(ledger, protocol, task):
    protocol, task, judge = configured(protocol, task)
    protocol = protocol.model_copy(update={"judgment_evidence_policy": "cohort-bound-v1"})
    run = saved_answer(ledger, protocol, task)
    sample = ledger.samples(run)[0]["id"]
    with pytest.raises(StateError, match="generation/cohort binding"):
        ledger.judge(sample, protocol.judge_digest, "pass", {})


def test_legacy_bare_judgment_is_reported_as_unbound(ledger, protocol, task):
    protocol, task, _ = configured(protocol, task)
    run = saved_answer(ledger, protocol, task)
    sample = ledger.samples(run)[0]["id"]
    ledger.judge(sample, protocol.judge_digest, "pass", {})
    report = ledger.summary(run)
    assert report["pass_at_1"] == 1
    assert report["judgment_evidence_policy"] is None
    assert report["judgment_evidence_binding"] == {"bound": 0, "legacy_unbound": 1}
    assert "judgment_evidence_unbound" in report["publication_blockers"]


@pytest.mark.parametrize("outcome", ["pass", "fail", "candidate_error", "timeout"])
def test_valid_captured_verdict_keeps_its_declared_outcome(ledger, protocol, task, outcome):
    protocol, task, judge = configured(protocol, task)
    protocol = protocol.model_copy(update={"judgment_evidence_policy": "cohort-bound-v1"})
    run = saved_answer(ledger, protocol, task)
    sample, evidence = bound_result(ledger, run, task, judge, outcome)
    ledger.judge(sample, protocol.judge_digest, outcome, evidence)
    report = ledger.summary(run)
    assert report["complete"]
    assert report["pass_at_1"] == (1 if outcome == "pass" else 0)
    assert report["judgment_evidence_binding"]["bound"] == 1


@pytest.mark.parametrize("outcome", ["pass", "fail"])
def test_native_scored_verdict_requires_a_captured_worker_result(outcome):
    manifest = {
        "track": "qhe-pinned-native-v1",
        "result_channel": "isolated-ephemeral-host-bind-v1",
    }
    evidence = {"manifest": manifest}
    with pytest.raises(ValueError, match="native worker result"):
        validate_judgment_result(outcome, evidence, identity(manifest))


def test_declared_binding_rejects_evidence_for_different_completion(ledger, protocol, task):
    protocol, task, judge = configured(protocol, task)
    protocol = protocol.model_copy(update={"judgment_evidence_policy": "cohort-bound-v1"})
    run = saved_answer(ledger, protocol, task)
    sample, evidence = bound_result(ledger, run, task, judge)
    evidence["judgment"]["completion_sha256"] = hashlib.sha256(b"different answer").hexdigest()
    with pytest.raises(StateError, match="completion"):
        ledger.judge(sample, protocol.judge_digest, "pass", evidence)


def test_native_worker_status_rewrite_must_match_retained_artifact():
    manifest = {"track": "qhe-pinned-native-v1"}
    failed = {"status": "fail", "completed": True, "phase": "test"}
    evidence = {
        "manifest": manifest,
        "worker_result": {**failed, "status": "pass"},
        "result_artifact": {
            "name": "result.json",
            "capture": "isolated-ephemeral-host-bind-v1",
            "sha256": identity(failed),
            "size": len(canonical(failed)),
        },
    }
    with pytest.raises(ValueError, match="native.*artifact"):
        validate_judgment_result("pass", evidence, identity(manifest))


@pytest.mark.parametrize("cases", [None, [], [{"case_id": "one", "passed": False}]])
def test_protected_pass_requires_nonempty_passing_declared_case_results(cases):
    manifest = {"track": "graybench-protected-semantic-v1", "case_ids": ["one"]}
    evidence = {"manifest": manifest}
    if cases is not None:
        evidence["case_results"] = cases
    with pytest.raises(ValueError, match="case"):
        validate_judgment_result("pass", evidence, identity(manifest))


@pytest.mark.parametrize("flags", [(True, True), (True, False), (False, False)])
def test_protected_aggregate_matches_complete_ordered_boolean_case_roster(flags):
    manifest = {"track": "graybench-protected-semantic-v1", "case_ids": ["one", "two"]}
    evidence = {
        "manifest": manifest,
        "case_results": [
            {"case_id": case_id, "passed": flag}
            for case_id, flag in zip(manifest["case_ids"], flags, strict=True)
        ],
    }
    outcome = "pass" if all(flags) else "fail"
    validate_judgment_result(outcome, evidence, identity(manifest))
    with pytest.raises(ValueError, match="case"):
        validate_judgment_result(
            "fail" if outcome == "pass" else "pass", evidence, identity(manifest)
        )
    for changed in (
        evidence["case_results"][:-1],
        evidence["case_results"][::-1],
        [evidence["case_results"][0]] * 2,
        [{"case_id": "one", "passed": 1}, evidence["case_results"][1]],
    ):
        with pytest.raises(ValueError, match="case"):
            validate_judgment_result(
                outcome, {**evidence, "case_results": changed}, identity(manifest)
            )


def test_native_unicode_artifact_uses_pinned_worker_serialization():
    manifest = {"track": "qhe-pinned-native-v1"}
    worker = {"status": "candidate_error", "completed": True, "phase": "test", "detail": "é"}
    raw = json.dumps(worker, sort_keys=True, separators=(",", ":")).encode()
    evidence = {
        "manifest": manifest,
        "worker_result": worker,
        "result_artifact": {
            "name": "result.json",
            "capture": "isolated-ephemeral-host-bind-v1",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        },
    }
    validate_judgment_result("candidate_error", evidence, identity(manifest))
    evidence["result_artifact"]["sha256"] = identity(worker)
    with pytest.raises(ValueError, match="artifact"):
        validate_judgment_result("candidate_error", evidence, identity(manifest))


def test_nested_capture_completion_hash_cannot_disagree_with_saved_answer(protocol, task):
    _, task, judge = configured(protocol, task)
    inner = captured(judge, task)
    manifest = {"track": "wrapper-fixture", "inner": inner["manifest"]}
    evidence = {"manifest": manifest, "inner": inner}
    validate_judgment_result(
        "pass",
        evidence,
        identity(manifest),
        completion="def answer(x): return x+1",
        require_completion=True,
    )
    inner["completion_sha256"] = hashlib.sha256(b"different completion").hexdigest()
    with pytest.raises(ValueError, match="completion"):
        validate_judgment_result(
            "pass",
            evidence,
            identity(manifest),
            completion="def answer(x): return x+1",
            require_completion=True,
        )

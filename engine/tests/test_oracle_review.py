import json
import os
from pathlib import Path

import pytest
from test_native_cohort import cache as _synthetic_cache

from graybench.cli import main
from graybench.datasets import JudgeTask, load_suite
from graybench.identity import canonical, identity
from graybench.judge import Judgment
from graybench.oracle_review import (
    CircuitSizeJudge,
    Probe,
    inspect_oracle_review,
    probes,
    run_review,
)


def private(task):
    return JudgeTask(
        public=task.model_copy(update={"entry_point": "create_quantum_circuit"}),
        canonical_solution="unused",
        upstream_test="def check(candidate):\n    assert candidate(3).num_qubits == 3",
        upstream_difficulty="fixture",
    )


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
@pytest.mark.parametrize("index", [0, 1, 2])
def test_size_revision_rejects_constant_and_accepts_register_and_gated_alternatives(task, index):
    record = private(task)
    probe = probes(record)[index]
    judge = CircuitSizeJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
    )
    result = judge.evaluate(record, probe.completion)
    assert result.outcome == probe.expectation, result
    assert result.evidence["manifest"]["release_eligible"] is False
    assert result.evidence["manifest"]["source"]["digest"]


def test_review_log_distinguishes_expected_failure_from_actual_pass(tmp_path, task):
    class AcceptsEverything:
        def evaluate(self, *_):
            return Judgment("pass", "0" * 64, {})

    record = private(task)
    output = tmp_path / "review.jsonl"
    summary = run_review((record,), AcceptsEverything(), output)
    assert summary["complete"] and summary["planned"] == 3
    records = [json.loads(line)["event"] for line in output.read_text().splitlines()]
    header = records[0]
    case = next(iter(header["selection"]["cases"].values()))
    assert case["task_digest"] == record.digest
    assert case["expectation"] == "fail"
    first = next(r for r in records if r["kind"] == "result")
    assert first["outcome"] == "pass"
    assert first["evidence"]["matches_expectation"] is False
    assert "not model scoring" in header["purpose"]


@pytest.fixture
def cache(tmp_path, monkeypatch):
    return _synthetic_cache.__wrapped__(tmp_path, monkeypatch)


def _review_log(tmp_path, cache, *, wrong_outcome=None):
    class ProbeJudge:
        def evaluate(self, _task, completion):
            outcome = "pass" if "QuantumCircuit(3)" not in completion else "fail"
            if wrong_outcome and "QuantumCircuit(3)" in completion:
                outcome = wrong_outcome
            return Judgment(outcome, "0" * 64, {})

    output = tmp_path / "review.jsonl"
    run_review((load_suite("normal", cache)[0],), ProbeJudge(), output)
    return output


def _rewrite_chain(path, mutate):
    records = [json.loads(line) for line in path.read_text().splitlines()]
    mutate(records)
    previous = "0" * 64
    for record in records:
        record["previous"] = previous
        record["digest"] = identity(
            {key: value for key, value in record.items() if key != "digest"}
        )
        previous = record["digest"]
    path.write_bytes(b"\n".join(canonical(record) for record in records) + b"\n")


@pytest.mark.parametrize("wrapped", [False, True])
def test_rechained_outcome_must_agree_with_captured_trusted_message(tmp_path, cache, wrapped):
    from graybench.upstream_evidence import CAPTURE, capture_judgment

    class CapturedJudge:
        def evaluate(self, *_):
            raw = b'{"kind":"judgment","outcome":"fail","evidence":{"calls":1}}\n'
            message, artifact = capture_judgment(raw, limit=4096)
            manifest = {"trusted_judgment_capture": CAPTURE, "output_limit": 4096}
            evidence = {
                **message["evidence"],
                "manifest": manifest,
                "trusted_judgment": message,
                "trusted_judgment_artifact": artifact,
                "termination_source": "trusted_judgment",
            }
            if wrapped:
                manifest = {"track": "fixture", "inner": manifest}
                evidence = {"manifest": manifest, "inner": evidence}
            return Judgment("fail", identity(manifest), evidence)

    output = tmp_path / "captured.jsonl"
    run_review(
        (load_suite("normal", cache)[0],),
        CapturedJudge(),
        output,
        probes_for=lambda _: (Probe("wrong", "fail", "Deliberately wrong", "return 0"),),
    )
    assert inspect_oracle_review(output, cache)["controls_matching_expectation"] == 1

    def mutate(records):
        result = next(r["event"] for r in records if r["event"]["kind"] == "result")
        result["outcome"] = "pass"
        result["evidence"]["matches_expectation"] = False

    _rewrite_chain(output, mutate)
    with pytest.raises(ValueError, match="trusted judgment"):
        inspect_oracle_review(output, cache)


def test_host_failure_without_terminal_capture_remains_inspectable(tmp_path, cache):
    from graybench.upstream_evidence import CAPTURE

    class HostFailure:
        def evaluate(self, *_):
            manifest = {"trusted_judgment_capture": CAPTURE, "output_limit": 4096}
            return Judgment(
                "infrastructure_error",
                identity(manifest),
                {
                    "manifest": manifest,
                    "detail": "trusted process could not start",
                    "termination_source": "host_error",
                },
            )

    output = tmp_path / "host-failure.jsonl"
    run_review(
        (load_suite("normal", cache)[0],),
        HostFailure(),
        output,
        probes_for=lambda _: (Probe("correct", "pass", "Valid control", "return 0"),),
    )
    report = inspect_oracle_review(output, cache)
    assert report["controls_matching_expectation"] == 0
    assert report["unexpected_outcomes"][0]["actual"] == "infrastructure_error"


@pytest.mark.parametrize("edit", ["candidate-capture", "wrapped-inner"])
def test_declared_terminal_capture_cannot_be_deleted_from_error_or_wrapper(tmp_path, cache, edit):
    from graybench.upstream_evidence import CAPTURE, capture_judgment

    outcome = "candidate_error" if edit == "candidate-capture" else "pass"

    class CapturedJudge:
        def evaluate(self, *_):
            raw = (
                json.dumps({"kind": "judgment", "outcome": outcome, "evidence": {"calls": 1}})
                + "\n"
            ).encode()
            message, artifact = capture_judgment(raw, limit=4096)
            inner_manifest = {"trusted_judgment_capture": CAPTURE, "output_limit": 4096}
            inner = {
                **message["evidence"],
                "manifest": inner_manifest,
                "trusted_judgment": message,
                "trusted_judgment_artifact": artifact,
                "termination_source": "trusted_judgment",
            }
            manifest = {"track": "fixture", "inner": inner_manifest}
            return Judgment(outcome, identity(manifest), {"manifest": manifest, "inner": inner})

    output = tmp_path / "capture-removed.jsonl"
    run_review(
        (load_suite("normal", cache)[0],),
        CapturedJudge(),
        output,
        probes_for=lambda _: (Probe("control", outcome, "Declared control", "return 0"),),
    )
    assert inspect_oracle_review(output, cache)["controls_matching_expectation"] == 1

    def mutate(records):
        result = next(r["event"] for r in records if r["event"]["kind"] == "result")
        judgment = result["evidence"]["judgment"]
        if edit == "wrapped-inner":
            del judgment["inner"]
        else:
            del judgment["inner"]["trusted_judgment"]
            del judgment["inner"]["trusted_judgment_artifact"]

    _rewrite_chain(output, mutate)
    with pytest.raises(ValueError, match="trusted judgment"):
        inspect_oracle_review(output, cache)


def test_local_oracle_verifier_checks_pinned_ancestry_and_outcomes(tmp_path, cache):
    output = _review_log(tmp_path, cache)
    report = inspect_oracle_review(output, cache)
    assert report["locally_verified"] is True
    assert report["independent_review"] is False
    assert report["publication_eligible"] is False
    assert report["control_count"] == 3
    assert report["controls"][0]["case_digest"]
    assert report["controls"][0]["task_digest"] == load_suite("normal", cache)[0].digest
    assert report["expected_failures"] == 1
    assert report["expected_passes"] == 2
    assert set(report["task_keys"]) == {"normal/qiskitHumanEval/0"}


def test_local_oracle_verifier_reports_when_log_source_is_historical(tmp_path, cache, monkeypatch):
    output = _review_log(tmp_path, cache)
    assert inspect_oracle_review(output, cache)["source_matches_running_source"] is True
    monkeypatch.setattr(
        "graybench.oracle_review.source_manifest",
        lambda: {"files": {}, "digest": "0" * 64},
    )
    stale = inspect_oracle_review(output, cache)
    assert stale["locally_verified"] is True
    assert stale["source_matches_running_source"] is False


def test_local_oracle_verifier_records_expected_malformed_candidate_separately(tmp_path, cache):
    class RejectsEmpty:
        def evaluate(self, *_):
            return Judgment("candidate_error", "0" * 64, {})

    output = tmp_path / "malformed.jsonl"
    source = load_suite("normal", cache)[0]
    run_review(
        (source,),
        RejectsEmpty(),
        output,
        probes_for=lambda _: (
            Probe("empty", "candidate_error", "An empty response violates shape", "return []"),
        ),
    )
    report = inspect_oracle_review(output, cache)
    assert report["control_count"] == 1
    assert report["controls_matching_expectation"] == 1
    assert report["expected_failures"] == 0
    assert report["expected_passes"] == 0
    assert report["expected_candidate_errors"] == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length paths only")
def test_local_oracle_verifier_reads_log_beyond_windows_legacy_path_limit(tmp_path, cache):
    source = _review_log(tmp_path, cache)
    long_path = tmp_path
    while len(str(long_path / "review.jsonl")) <= 280:
        long_path = long_path / ("x" * 80)
    long_path = long_path / "review.jsonl"
    extended = Path("\\\\?\\" + str(long_path.absolute()))
    extended.parent.mkdir(parents=True)
    extended.write_bytes(source.read_bytes())

    report = inspect_oracle_review(long_path, cache)
    assert report["locally_verified"] is True
    assert report["control_count"] == 3


@pytest.mark.parametrize("actual", ["pass", "timeout"])
def test_local_oracle_verifier_reports_actual_mismatch(tmp_path, cache, actual):
    output = _review_log(tmp_path, cache, wrong_outcome=actual)
    report = inspect_oracle_review(output, cache)
    assert report["locally_verified"] is True
    assert report["controls_matching_expectation"] == 2
    assert report["unexpected_outcomes"] == [
        {
            "task_key": "normal/qiskitHumanEval/0/constant-three",
            "expected": "fail",
            "actual": actual,
        }
    ]


def test_local_oracle_verifier_rejects_rechained_false_result_or_ancestry(tmp_path, cache):
    output = _review_log(tmp_path, cache)
    _rewrite_chain(
        output,
        lambda records: next(record for record in records if record["event"]["kind"] == "result")[
            "event"
        ].update(outcome="pass"),
    )
    with pytest.raises(ValueError, match="expectation"):
        inspect_oracle_review(output, cache)

    output.unlink()
    output = _review_log(tmp_path, cache)

    def change_ancestry(records):
        key = "normal/qiskitHumanEval/0/constant-three"
        header = records[0]["event"]
        header["selection"]["cases"][key]["task_digest"] = "f" * 64
        header["tasks"][key] = identity(header["selection"]["cases"][key])

    _rewrite_chain(output, change_ancestry)
    with pytest.raises(ValueError, match="digest"):
        inspect_oracle_review(output, cache)


def test_oracle_review_cli_reports_local_scope(tmp_path, cache, monkeypatch, capsys):
    import sys

    output = _review_log(tmp_path, cache)
    monkeypatch.setattr(
        sys, "argv", ["graybench", "oracle-review-inspect", str(output), str(cache)]
    )
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["locally_verified"] is True
    assert result["independent_review"] is False
    assert result["publication_eligible"] is False


def test_local_oracle_verifier_rejects_nonstring_judge_digest_and_source_file(tmp_path, cache):
    output = _review_log(tmp_path, cache)

    def change_judge_digest(records):
        result = next(record for record in records if record["event"]["kind"] == "result")
        result["event"]["judge_digest"] = int("1" * 64)

    _rewrite_chain(output, change_judge_digest)
    with pytest.raises(ValueError, match="judgment evidence"):
        inspect_oracle_review(output, cache)

    output.unlink()
    output = _review_log(tmp_path, cache)

    def change_source_file(records):
        header = records[0]["event"]
        header["source"]["files"]["forged.py"] = None
        header["source"]["digest"] = identity(header["source"]["files"])

    _rewrite_chain(output, change_source_file)
    with pytest.raises(ValueError, match="source manifest"):
        inspect_oracle_review(output, cache)


def test_protected_control_log_predeclares_judge_before_execution(tmp_path, cache):
    task = load_suite("normal", cache)[0]
    task_key = f"{task.public.suite}/{task.public.task_id}"
    manifest = {
        "track": "graybench-protected-semantic-v1",
        "source_task_digest": task.digest,
        "public_contract_digest": "a" * 64,
        "oracle": "fixture-v1",
        "private_case_digest": "b" * 64,
    }

    class Judge:
        def evaluate(self, _task, _completion):
            return Judgment("pass", identity(manifest), {"manifest": manifest})

    output = tmp_path / "protected.jsonl"
    run_review(
        (task,),
        Judge(),
        output,
        probes_for=lambda _task: (Probe("valid", "pass", "Correct value", "def answer(): pass"),),
        declared_judges={task_key: manifest},
    )
    report = inspect_oracle_review(output, cache)
    assert report["controls"][0]["judge_predeclared"] is True
    assert report["controls"][0]["judge_digest"] == identity(manifest)

    def alter_declared_manifest(records):
        header = records[0]["event"]
        header["selection"]["declared_judges"][task_key]["oracle"] = "fixture-v0"

    _rewrite_chain(output, alter_declared_manifest)
    with pytest.raises(ValueError, match="declared judge"):
        inspect_oracle_review(output, cache)


def test_protected_control_run_stops_on_unexpected_judge_digest(tmp_path, cache):
    task = load_suite("normal", cache)[0]
    task_key = f"{task.public.suite}/{task.public.task_id}"
    manifest = {
        "track": "graybench-protected-semantic-v1",
        "source_task_digest": task.digest,
        "public_contract_digest": "a" * 64,
    }

    class ChangedJudge:
        def evaluate(self, _task, _completion):
            return Judgment("pass", "0" * 64, {"manifest": manifest})

    output = tmp_path / "incomplete.jsonl"
    with pytest.raises(ValueError, match="declared judge"):
        run_review(
            (task,),
            ChangedJudge(),
            output,
            probes_for=lambda _task: (Probe("valid", "pass", "Correct value", "code"),),
            declared_judges={task_key: manifest},
        )
    with pytest.raises(ValueError, match="incomplete"):
        inspect_oracle_review(output, cache)

import json
import sys

import pytest
from test_native_cohort import cache as _native_cache

from graybench.cli import main
from graybench.datasets import JudgeTask
from graybench.judge import Judgment
from graybench.native_judge import NativeJudge
from graybench.reference_scan import (
    inspect_reference_scan,
    run_native_reference_scan,
    run_reference_scan,
)


@pytest.fixture
def native_cache(tmp_path, monkeypatch):
    return _native_cache.__wrapped__(tmp_path, monkeypatch)


def test_native_reference_scan_freezes_literal_normal_condition(
    native_cache, tmp_path, monkeypatch
):
    def docker_boundary(self, wire, digest, evidence):
        payload = json.loads(wire)
        assert payload["suite"] == "normal"
        assert payload["code"].endswith("    return 4\n")
        return Judgment("pass", digest, evidence)

    monkeypatch.setattr(NativeJudge, "_execute", docker_boundary)
    output = tmp_path / "native-scan.jsonl"
    summary = run_native_reference_scan(
        native_cache,
        output,
        suite="normal",
        image="sha256:" + "a" * 64,
        extraction="exact_prompt_suffix_v1",
        task_keys=("normal/qiskitHumanEval/4",),
    )
    assert summary["complete"] is True
    assert summary["planned"] == 1
    assert summary["results"] == {"normal/qiskitHumanEval/4": "pass"}
    events = [json.loads(line)["event"] for line in output.read_text().splitlines()]
    selection = events[0]["selection"]
    assert selection["track"] == "qhe-pinned-native-v1"
    assert selection["cohort"]["suite"] == "normal"
    assert selection["cohort"]["extraction"] == "exact_prompt_suffix_v1"
    assert selection["cohort"]["task_keys"] == ["normal/qiskitHumanEval/4"]
    assert len(selection["cohort"]["excluded"]) == 150
    assert events[2]["evidence"]["manifest"]["cohort_digest"] == selection["cohort_digest"]


def test_native_reference_scan_rejects_invalid_policy_before_writing(native_cache, tmp_path):
    output = tmp_path / "invalid.jsonl"
    with pytest.raises(ValueError, match="normal suite"):
        run_native_reference_scan(
            native_cache,
            output,
            suite="hard",
            image="sha256:" + "a" * 64,
            extraction="exact_prompt_suffix_v1",
            task_keys=("hard/qiskitHumanEval/4",),
        )
    assert not output.exists()


def test_native_reference_scan_never_silently_includes_external_task(native_cache, tmp_path):
    output = tmp_path / "external.jsonl"
    with pytest.raises(ValueError, match="--include-external"):
        run_native_reference_scan(
            native_cache,
            output,
            suite="normal",
            image="sha256:" + "a" * 64,
            extraction="exact_prompt_suffix_v1",
            task_keys=("normal/qiskitHumanEval/43",),
        )
    assert not output.exists()


def test_native_reference_scan_cli_writes_one_source_bound_case(
    native_cache, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        NativeJudge,
        "_execute",
        lambda self, wire, digest, evidence: Judgment("pass", digest, evidence),
    )
    output = tmp_path / "cli-native-scan.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "native-reference-scan",
            str(native_cache),
            str(output),
            "--suite",
            "normal",
            "--image",
            "sha256:" + "a" * 64,
            "--extraction",
            "exact_prompt_suffix_v1",
            "--exception-policy",
            "test_exception_is_failure_v1",
            "--task",
            "normal/qiskitHumanEval/4",
        ],
    )
    main()
    printed = json.loads(capsys.readouterr().out)
    assert printed["complete"] is True
    assert printed["results"] == {"normal/qiskitHumanEval/4": "pass"}
    assert printed["exception_policy"] == "test_exception_is_failure_v1"
    assert output.exists()
    header = json.loads(output.read_text().splitlines()[0])["event"]
    assert header["selection"]["cohort"]["exception_policy"] == "test_exception_is_failure_v1"


def test_native_reference_scan_cli_requires_explicit_answer_format(
    native_cache, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        NativeJudge,
        "_execute",
        lambda self, wire, digest, evidence: Judgment("pass", digest, evidence),
    )
    output = tmp_path / "unspecified-policy.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "native-reference-scan",
            str(native_cache),
            str(output),
            "--suite",
            "normal",
            "--image",
            "sha256:" + "a" * 64,
            "--task",
            "normal/qiskitHumanEval/4",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    assert not output.exists()


def private(task):
    return JudgeTask(
        public=task,
        canonical_solution="reference",
        upstream_test="test",
        upstream_difficulty="fixture",
    )


class Judge:
    def __init__(self):
        self.calls = 0

    def evaluate(self, task, code):
        self.calls += 1
        assert code == task.canonical_solution
        return Judgment("pass", "0" * 64, {"fixture": True})


def test_reference_log_is_complete_and_never_overwritten(tmp_path, task):
    output = tmp_path / "scan.jsonl"
    judge = Judge()
    summary = run_reference_scan((private(task),), judge, output)
    assert summary["complete"]
    assert summary["planned"] == 1
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        run_reference_scan((private(task),), judge, output)
    assert judge.calls == 1
    assert output.read_bytes() == before
    assert inspect_reference_scan(output) == summary


def test_interrupted_reference_remains_pending(tmp_path, task):
    class Interrupted:
        def evaluate(self, *_):
            raise KeyboardInterrupt()

    output = tmp_path / "scan.jsonl"
    with pytest.raises(KeyboardInterrupt):
        run_reference_scan((private(task),), Interrupted(), output)
    result = inspect_reference_scan(output)
    assert not result["complete"]
    assert result["pending_task"] == "hard/qiskitHumanEval/0"
    assert result["results"] == {}


@pytest.mark.parametrize("corruption", ["truncate", "modify"])
def test_damaged_evidence_is_not_reported_complete(tmp_path, task, corruption):
    output = tmp_path / "scan.jsonl"
    run_reference_scan((private(task),), Judge(), output)
    data = output.read_bytes()
    if corruption == "truncate":
        output.write_bytes(data[:-3])
    else:
        records = [json.loads(line) for line in data.splitlines()]
        records[2]["event"]["outcome"] = "fail"
        output.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    with pytest.raises(ValueError):
        inspect_reference_scan(output)

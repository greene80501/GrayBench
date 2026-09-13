import json

import pytest

from graybench.datasets import JudgeTask
from graybench.judge import Judgment
from graybench.reference_scan import inspect_reference_scan, run_reference_scan


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

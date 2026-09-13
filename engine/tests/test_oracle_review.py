import json
import os

import pytest

from graybench.datasets import JudgeTask
from graybench.judge import Judgment
from graybench.oracle_review import CircuitSizeJudge, probes, run_review


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

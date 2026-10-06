"""Literal-mutant controls must be paired with the calibrated native cohorts."""

import hashlib
import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from graybench.identity import canonical, identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "docs/reliability-evidence/native_literal_mutant_screen.py"
ARTIFACT = (
    ROOT / "docs/reliability-evidence/artifacts/native-literal-mutants-2026-10-06-v2/results.jsonl"
)
SCORED_ARTIFACT = (
    ROOT
    / "docs/reliability-evidence/artifacts/native-literal-mutants-scored-2026-10-06/results.jsonl"
)


def load_script():
    spec = importlib.util.spec_from_file_location("native_literal_mutant_screen", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_literal_mutants_share_current_reference_cohorts():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    cases, _, cohorts = module.plan(cache)
    assert len(cases) == len({item[0] for item in cases}) == 572
    assert {suite: cohort.digest for suite, cohort in cohorts.items()} == {
        "normal": "a3fbe24e4f69fa75f4ee2f713298b2578b8242b9cb28ce27249da8bf73347adb",
        "hard": "000fbb069089ea49609ad1864d12a89532aeb4c979426bad05a6c0f9a8b9cdbd",
    }
    assert all(item[0].endswith(("/zero", "/empty_list")) for item in cases)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_literal_mutant_scored_policy_changes_only_declared_cohort_condition():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    original_cases, _, original_cohorts = module.plan(cache)
    scored_cases, _, scored_cohorts = module.plan(
        cache, exception_policy="test_exception_is_failure_v1"
    )
    assert [(key, digest, answer) for key, digest, answer in original_cases] == [
        (key, digest, answer) for key, digest, answer in scored_cases
    ]
    for suite in ("normal", "hard"):
        original = original_cohorts[suite]
        scored = scored_cohorts[suite]
        assert original.exception_policy == "conservative_unattributed_v1"
        assert scored.exception_policy == "test_exception_is_failure_v1"
        assert scored.digest != original.digest
        assert scored.model_copy(update={"exception_policy": original.exception_policy}) == original
    assert "exception_policy" not in module.selection(original_cohorts)
    assert module.selection(scored_cohorts)["exception_policy"] == ("test_exception_is_failure_v1")


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_literal_mutant_results_and_rehashed_outcome_tamper(tmp_path):
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    report = module.verify(cache, ARTIFACT)
    assert report["complete"] is True
    assert report["planned"] == 572
    assert report["publication_eligible"] is False
    assert report["outcomes"] == {"fail": 366, "infrastructure_error": 202, "pass": 4}
    assert report["completed_test_phase_infrastructure_count"] == 202
    assert report["other_infrastructure_count"] == 0
    assert report["passes"] == [
        f"{suite}/qiskitHumanEval/{number}/empty_list"
        for suite in ("hard", "normal")
        for number in (110, 139)
    ]

    records = [json.loads(line) for line in ARTIFACT.read_bytes().splitlines()]
    changed = False
    previous = "0" * 64
    for record in records:
        event = record["event"]
        if event["kind"] == "result" and not changed:
            event["outcome"] = "pass" if event["outcome"] != "pass" else "fail"
            changed = True
        record["previous"] = previous
        record["digest"] = identity(
            {key: value for key, value in record.items() if key != "digest"}
        )
        previous = record["digest"]
    assert changed
    forged = tmp_path / "forged.jsonl"
    forged.write_bytes(b"".join(canonical(record) + b"\n" for record in records))
    with pytest.raises(ValueError, match="pass differs from worker"):
        module.verify(cache, forged)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_literal_mutant_verifier_rejects_rehashed_nonpass_change(tmp_path):
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    records = [json.loads(line) for line in ARTIFACT.read_bytes().splitlines()]
    changed = False
    previous = "0" * 64
    for record in records:
        event = record["event"]
        if event["kind"] == "result" and event["outcome"] == "fail" and not changed:
            assert event["evidence"]["worker_result"]["status"] == "fail"
            event["outcome"] = "infrastructure_error"
            changed = True
        record["previous"] = previous
        record["digest"] = identity(
            {key: value for key, value in record.items() if key != "digest"}
        )
        previous = record["digest"]
    assert changed
    forged = tmp_path / "forged-nonpass.jsonl"
    forged.write_bytes(b"".join(canonical(record) + b"\n" for record in records))
    with pytest.raises(ValueError, match="outcome differs from worker"):
        module.verify(cache, forged)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_literal_mutant_policy_comparison_is_paired_and_source_bound():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    conservative = module.verify(cache, ARTIFACT)
    scored = module.verify(cache, SCORED_ARTIFACT)
    assert conservative["exception_policy"] == "conservative_unattributed_v1"
    assert scored["exception_policy"] == "test_exception_is_failure_v1"
    assert conservative["source_digest"] == scored["source_digest"]
    assert conservative["image"] == scored["image"]
    assert conservative["planned"] == scored["planned"] == 572
    assert scored["outcomes"] == {"fail": 568, "pass": 4}
    assert scored["completed_test_phase_infrastructure_count"] == 0
    assert scored["passes"] == conservative["passes"]
    scored_header = json.loads(SCORED_ARTIFACT.open("rb").readline())["event"]
    assert (
        hashlib.sha256((SCORED_ARTIFACT.parent / "probe.py").read_bytes()).hexdigest()
        == scored_header["selection"]["probe_sha256"]
    )

    def rows(path):
        records = (json.loads(line)["event"] for line in path.read_bytes().splitlines())
        return {event["task_key"]: event for event in records if event["kind"] == "result"}

    earlier, later = rows(ARTIFACT), rows(SCORED_ARTIFACT)
    assert set(earlier) == set(later)
    assert Counter((earlier[key]["outcome"], later[key]["outcome"]) for key in earlier) == {
        ("fail", "fail"): 366,
        ("infrastructure_error", "fail"): 202,
        ("pass", "pass"): 4,
    }
    for key in earlier:
        before, after = earlier[key]["evidence"], later[key]["evidence"]
        assert before["worker_result"] is not None
        assert after["worker_result"] is not None
        assert earlier[key]["outcome"] == before["worker_result"]["status"]
        assert later[key]["outcome"] == after["worker_result"]["status"]
        for field in ("completion_sha256", "code_sha256", "extraction_method"):
            assert before[field] == after[field]
        assert before["manifest"]["task_digest"] == after["manifest"]["task_digest"]
        assert before["manifest"]["image"] == after["manifest"]["image"]


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_scored_literal_chain_survives_future_probe_edits(tmp_path, monkeypatch):
    module = load_script()
    changed = tmp_path / "future_probe.py"
    changed.write_bytes(SCRIPT.read_bytes() + b"\n# A later diagnostic revision\n")
    monkeypatch.setattr(module, "__file__", str(changed))
    report = module.verify(Path(os.environ["GRAYBENCH_TEST_CACHE"]), SCORED_ARTIFACT)
    assert report["outcomes"] == {"fail": 568, "pass": 4}

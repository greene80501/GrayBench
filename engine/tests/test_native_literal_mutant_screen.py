"""Literal-mutant controls must be paired with the calibrated native cohorts."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from graybench.identity import canonical, identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "docs/reliability-evidence/native_literal_mutant_screen.py"
ARTIFACT = (
    ROOT / "docs/reliability-evidence/artifacts/native-literal-mutants-2026-10-05/results.jsonl"
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
        "normal": "cc8009ebcc2bffdc0ec843d087c35d3ea52f470fe73f823084a9766131efe16a",
        "hard": "fbb41b77ccd613b8dc7aa54009839911a5795661be93eb1ab7bc8a0104038b1f",
    }
    assert all(item[0].endswith(("/zero", "/empty_list")) for item in cases)


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

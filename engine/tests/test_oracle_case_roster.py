"""The review roster is exact evidence of calls, not an admission decision."""

import copy
import importlib.util
import json
import os
from pathlib import Path

import pytest

from graybench.admission_bundle import verify_admission_bundle
from graybench.datasets import load_suite
from graybench.identity import canonical, identity
from graybench.protected_task_registry import revised_value_task
from graybench.provenance import source_manifest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "docs/reliability-evidence/build_oracle_case_roster_2026_10_06.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location("oracle_case_roster", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_historical_roster_preserves_six_cards_and_exact_private_calls():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    packet = json.loads(
        (SCRIPT.parent / "artifacts/oracle-case-roster-2026-10-06-v2.json").read_bytes()
    )
    report = verify_admission_bundle(module.BUNDLE, cache)
    assert report["verified"] and not report["inventory_source_matches_running_source"]
    inventory = json.loads((module.BUNDLE / "inventory.json").read_bytes())
    assert packet["source_digest"] == inventory["source_digest"]
    for row in packet["tasks"]:
        suite, _, number = row["source_key"].split("/")
        source = load_suite(suite, cache)[int(number)]
        task = revised_value_task(source)
        assert row["source_task_digest"] == source.digest
        assert row["public_contract_digest"] == task.contract.digest
        expected = [
            {
                "case_id": case.case_id,
                "call": case.call.model_dump(mode="json"),
                "digest": identity(case.model_dump(mode="json")),
            }
            for case in task.cases
        ]
        assert canonical(row["cases"]) == canonical(expected)
    assert packet["publication_eligible"] is False
    assert packet["independent_review"] is False
    assert [len(task["cases"]) for task in packet["tasks"]] == [1, 210, 1364, 1, 210, 1364]
    assert len({case["digest"] for task in packet["tasks"] for case in task["cases"]}) == 1575
    assert all(task["requirements"] for task in packet["tasks"])
    assert all(task["requirement_case_links"] == [] for task in packet["tasks"])


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_historical_roster_cannot_be_reused_as_a_current_source_packet():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    packet = json.loads(
        (SCRIPT.parent / "artifacts/oracle-case-roster-2026-10-06-v2.json").read_bytes()
    )
    with pytest.raises(ValueError, match="current pinned source"):
        module.verify(packet, cache)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_roster_verifier_rejects_changed_case_against_expected_current_fixture(monkeypatch):
    """Isolate the exact-packet comparison from the historical builder's source gate."""
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    expected = json.loads(
        (SCRIPT.parent / "artifacts/oracle-case-roster-2026-10-06-v2.json").read_bytes()
    )
    # Synthetic expected build output, only in memory; not fresh execution evidence.
    expected["source_digest"] = source_manifest()["digest"]
    monkeypatch.setattr(module, "build", lambda _: copy.deepcopy(expected))
    assert module.verify(copy.deepcopy(expected), cache)
    changed = copy.deepcopy(expected)
    changed["tasks"][0]["cases"][0]["case_id"] = "changed"
    with pytest.raises(ValueError, match="Oracle case roster differs"):
        module.verify(changed, cache)

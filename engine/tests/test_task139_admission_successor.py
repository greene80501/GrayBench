"""Task 139 controls enter admission bookkeeping without a publication claim."""

import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

from graybench.admission_bundle import verify_admission_bundle
from graybench.task_admission import AdmissionInventory


def _module():
    script = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/refresh_admission_task139_2026_10_06.py"
    )
    spec = importlib.util.spec_from_file_location("task139_admission_successor", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_historical_task139_successor_binds_controls_without_reviews(tmp_path):
    module = _module()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    bundle = module.HERE / "artifacts/admission-task139-current-2026-10-06"
    _check_successor(module, cache, bundle)
    destination = tmp_path / "successor"
    with pytest.raises(ValueError, match="Predecessor source differs"):
        module.build(cache, destination)
    assert not destination.exists()


def _check_successor(module, cache, bundle):
    report = verify_admission_bundle(bundle, cache)
    assert report == verify_admission_bundle(bundle, cache)
    assert report["verified"] is True
    assert report["inventory_source_matches_running_source"] is False
    assert report["control_count"] == 82
    assert report["covered_task_count"] == 12
    assert report["uncovered_task_count"] == 290
    assert report["inventory_source_bound_control_count"] == 64
    assert report["false_pass_count"] == 8
    assert report["publication_eligible"] is False
    inventory = AdmissionInventory.model_validate_json((bundle / "inventory.json").read_bytes())
    predecessor_inventory = AdmissionInventory.model_validate_json(
        (module.PREDECESSOR / "inventory.json").read_bytes()
    )
    before = {card.source_key: card for card in predecessor_inventory.cards}
    assert all(
        card == before[card.source_key]
        for card in inventory.cards
        if not card.source_key.endswith("/qiskitHumanEval/139")
    )
    audit = json.loads((bundle / "audit.json").read_bytes())
    for suite in ("normal", "hard"):
        key = f"{suite}/qiskitHumanEval/139"
        card = next(card for card in inventory.cards if card.source_key == key)
        row = next(row for row in audit["tasks"] if row["task_key"] == key)
        assert card.public_contract_digest and card.protected_judge_digest
        assert len(card.requirements) == 1
        assert not card.reviews and not card.finding_resolutions
        assert len(row["controls"]) == 11
        assert sorted(control["expected"] for control in row["controls"]) == [
            "candidate_error",
            *(["fail"] * 5),
            *(["pass"] * 5),
        ]
        assert all(link["status"] == "matching_local_observation" for link in row["evidence_links"])
        linked = {
            *card.requirements[0].independent_alternative_digests,
            *card.requirements[0].wrong_mutant_digests,
        }
        assert len(linked) == 10
        assert all(
            control["case_digest"] not in linked
            for control in row["controls"]
            if control["expected"] == "candidate_error"
        )

    predecessor = json.loads((module.PREDECESSOR / "manifest.json").read_bytes())
    for descriptor in predecessor["reviews"]:
        name = descriptor["file"]
        assert (module.PREDECESSOR / name).read_bytes() == (bundle / name).read_bytes()


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_historical_task139_bundle_refuses_changed_control_log(tmp_path):
    module = _module()
    bundle = tmp_path / "changed-bundle"
    shutil.copytree(module.HERE / "artifacts/admission-task139-current-2026-10-06", bundle)
    changed = bundle / "protected-task139-current.jsonl"
    with changed.open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="file size or digest mismatch"):
        verify_admission_bundle(bundle, Path(os.environ["GRAYBENCH_TEST_CACHE"]))

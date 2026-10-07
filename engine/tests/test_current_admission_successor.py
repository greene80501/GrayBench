"""A current-source control log can refresh evidence without inventing reviews."""

import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

from graybench.admission_bundle import verify_admission_bundle
from graybench.task_admission import AdmissionInventory


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_historical_successor_preserves_six_value_cards_without_claiming_current_source(tmp_path):
    script = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/refresh_admission_2026_10_06.py"
    )
    spec = importlib.util.spec_from_file_location("current_admission_successor", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    bundle = script.parent / "artifacts/admission-current-controls-2026-10-06-v2"
    report = verify_admission_bundle(bundle, cache)
    assert report["verified"] is True
    assert report["inventory_source_matches_running_source"] is False
    assert report["inventory_source_bound_control_count"] == 42
    assert report["different_source_bound_control_count"] == 0
    assert report["control_count"] == 60
    assert report["covered_task_count"] == 10
    assert report["publication_eligible"] is False
    assert verify_admission_bundle(bundle, cache) == report
    destination = tmp_path / "successor"
    with pytest.raises(ValueError, match="current finding registry"):
        module.build(cache, destination)
    assert not destination.exists()


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_current_admission_successor_refuses_changed_control_log(tmp_path, monkeypatch):
    script = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/refresh_admission_2026_10_06.py"
    )
    spec = importlib.util.spec_from_file_location("current_admission_successor", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Exercise the historical byte guard under its own frozen registry.
    # The preceding test separately proves current use rejects that registry.
    manifest = json.loads((module.PREDECESSOR / "manifest.json").read_bytes())
    historical = AdmissionInventory.model_validate_json(
        module.read_pinned(module.PREDECESSOR / "inventory.json", manifest["inventory"])
    )
    monkeypatch.setattr(
        "graybench.task_admission.KNOWN_FINDINGS",
        {int(key): list(value) for key, value in historical.finding_registry.items()},
    )
    changed = tmp_path / "changed.jsonl"
    shutil.copyfile(module.CONTROLS, changed)
    with changed.open("ab") as stream:
        stream.write(b" ")
    monkeypatch.setattr(module, "CONTROLS", changed)
    destination = tmp_path / "rejected"
    with pytest.raises(ValueError, match="control bytes differ"):
        module.build(Path(os.environ["GRAYBENCH_TEST_CACHE"]), destination)
    assert not destination.exists()

"""A current-source control log can refresh evidence without inventing reviews."""

import importlib.util
import os
import shutil
from pathlib import Path

import pytest

from graybench.admission_bundle import verify_admission_bundle


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_current_admission_successor_rebinds_only_six_value_cards(tmp_path):
    script = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/refresh_admission_2026_10_05.py"
    )
    spec = importlib.util.spec_from_file_location("current_admission_successor", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    bundle = tmp_path / "successor"
    report = module.build(cache, bundle)
    assert report["verified"] is True
    assert report["inventory_source_matches_running_source"] is True
    assert report["inventory_source_bound_control_count"] == 42
    assert report["different_source_bound_control_count"] == 0
    assert report["control_count"] == 60
    assert report["covered_task_count"] == 10
    assert report["publication_eligible"] is False
    assert verify_admission_bundle(bundle, cache) == report


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_current_admission_successor_refuses_changed_control_log(tmp_path, monkeypatch):
    script = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/refresh_admission_2026_10_05.py"
    )
    spec = importlib.util.spec_from_file_location("current_admission_successor", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    changed = tmp_path / "changed.jsonl"
    shutil.copyfile(module.CONTROLS, changed)
    with changed.open("ab") as stream:
        stream.write(b" ")
    monkeypatch.setattr(module, "CONTROLS", changed)
    destination = tmp_path / "rejected"
    with pytest.raises(ValueError, match="control bytes differ"):
        module.build(Path(os.environ["GRAYBENCH_TEST_CACHE"]), destination)
    assert not destination.exists()

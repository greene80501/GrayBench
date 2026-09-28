"""A committed evidence bundle must replay to the exact saved admission audit."""

import hashlib
import json

import pytest
from test_native_cohort import cache as _synthetic_cache

import graybench.admission_bundle as bundle_module
from graybench.admission_bundle import verify_admission_bundle
from graybench.datasets import load_suite
from graybench.identity import canonical
from graybench.judge import Judgment
from graybench.oracle_review import run_review
from graybench.task_admission import audit_control_coverage, build_pending_inventory


@pytest.fixture
def cache(tmp_path, monkeypatch):
    return _synthetic_cache.__wrapped__(tmp_path, monkeypatch)


def _entry(path):
    data = path.read_bytes()
    return {"file": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _bundle(tmp_path, cache):
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    inventory = build_pending_inventory(cache)
    inventory_path = bundle / "inventory.json"
    inventory_path.write_bytes(canonical(inventory.model_dump(mode="json")))

    class ProbeJudge:
        def evaluate(self, _task, _completion):
            return Judgment("fail", "0" * 64, {})

    review_path = bundle / "review.jsonl"
    run_review((load_suite("normal", cache)[0],), ProbeJudge(), review_path)
    audit_path = bundle / "audit.json"
    audit_path.write_bytes(canonical(audit_control_coverage(inventory, cache, (review_path,))))
    manifest = {
        "schema_version": "1",
        "scope": "local authored controls; not model scoring",
        "inventory": _entry(inventory_path),
        "reviews": [_entry(review_path)],
        "audit": _entry(audit_path),
    }
    (bundle / "manifest.json").write_bytes(canonical(manifest))
    return bundle, manifest


def test_bundle_recomputes_exact_saved_audit(tmp_path, cache):
    bundle, _ = _bundle(tmp_path, cache)
    result = verify_admission_bundle(bundle, cache)
    assert result["verified"] is True
    assert result["control_count"] == 3
    assert result["false_pass_count"] == 0
    assert result["publication_eligible"] is False
    assert result["independent_review"] is False


def test_bundle_rejects_changed_log_and_rehashed_but_false_audit(tmp_path, cache):
    bundle, manifest = _bundle(tmp_path, cache)
    review = bundle / "review.jsonl"
    review.write_bytes(review.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest|size"):
        verify_admission_bundle(bundle, cache)

    bundle, manifest = _bundle(tmp_path / "second", cache)
    audit = bundle / "audit.json"
    altered = json.loads(audit.read_bytes())
    altered["control_count"] = 100
    audit.write_bytes(canonical(altered))
    manifest["audit"] = _entry(audit)
    (bundle / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match="recomputed audit"):
        verify_admission_bundle(bundle, cache)


def test_bundle_rejects_path_traversal_and_duplicate_review_file(tmp_path, cache):
    bundle, manifest = _bundle(tmp_path, cache)
    manifest["inventory"]["file"] = "../inventory.json"
    (bundle / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match="file name"):
        verify_admission_bundle(bundle, cache)

    manifest["inventory"]["file"] = "inventory.json"
    manifest["reviews"].append(manifest["reviews"][0])
    (bundle / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        verify_admission_bundle(bundle, cache)


def test_bundle_replays_verified_snapshot_and_rejects_source_changed_during_check(
    tmp_path, cache, monkeypatch
):
    bundle, _ = _bundle(tmp_path, cache)
    original_audit = bundle_module.audit_control_coverage

    def replace_original_after_hash(inventory, pinned_cache, review_paths):
        assert all(path.parent != bundle for path in review_paths)
        (bundle / "review.jsonl").write_bytes(b"changed after hash\n")
        return original_audit(inventory, pinned_cache, review_paths)

    monkeypatch.setattr(bundle_module, "audit_control_coverage", replace_original_after_hash)
    with pytest.raises(ValueError, match="changed during verification"):
        verify_admission_bundle(bundle, cache)


def test_bundle_caps_total_review_bytes(tmp_path, cache, monkeypatch):
    bundle, _ = _bundle(tmp_path, cache)
    monkeypatch.setattr(bundle_module, "_MAX_TOTAL_REVIEW_BYTES", 1)
    with pytest.raises(ValueError, match="total byte limit"):
        verify_admission_bundle(bundle, cache)

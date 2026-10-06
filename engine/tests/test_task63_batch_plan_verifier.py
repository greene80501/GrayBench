"""The predeclared batch plan is checked without executing a candidate."""

from pathlib import Path

import pytest
from graybench.identity import canonical


def verifier_module():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/artifacts/task63-batch-controls-2026-10-05/verify.py"
    )
    spec = importlib.util.spec_from_file_location("task63_batch_plan_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_batch_plan_is_predeclared_without_result_claim():
    report = verifier_module().verify()
    assert report["predeclared"] is True
    assert report["controls_executed"] is False
    assert report["control_count"] == 16
    assert report["expected_outcomes"] == {"pass": 6, "fail": 8, "candidate_error": 2}
    assert report["publication_eligible"] is False


def test_byte_tampered_batch_plan_is_rejected(tmp_path):
    verifier = verifier_module()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    source = verifier.HERE / "plan.json"
    raw = source.read_bytes()
    (bundle / "plan.json").write_bytes(raw[:-2] + b" \n")
    with pytest.raises(ValueError, match="byte|digest"):
        verifier.verify(bundle)


def test_semantically_changed_batch_plan_is_rejected_by_pinned_digest(tmp_path):
    verifier = verifier_module()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    plan = verifier.read_plan(verifier.HERE / "plan.json")
    plan["cases"]["hard/63/fixed-one"]["expected"] = "pass"
    (bundle / "plan.json").write_bytes(canonical(plan) + b"\n")
    with pytest.raises(ValueError, match="byte|digest|outcome"):
        verifier.verify(bundle)

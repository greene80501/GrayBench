import importlib.util
import os
from pathlib import Path

import pytest

from graybench.datasets import KNOWN_FINDINGS, KNOWN_FINDINGS_V2, load_suite

SCRIPT = (
    Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task12_operator_ambiguity.py"
)


def test_current_task12_finding_does_not_rewrite_frozen_v2():
    assert 12 not in KNOWN_FINDINGS_V2
    assert 12 in KNOWN_FINDINGS
    assert any("unstated" in finding and "operator" in finding for finding in KNOWN_FINDINGS[12])


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Needs exact pinned QHE")
def test_task12_exact_checks_and_independent_bell_preparation_calibration():
    spec = importlib.util.spec_from_file_location("task12_operator_ambiguity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    report = module.build(cache)
    assert len(report["controls"]) == 5
    assert report["publication_eligible"] is False
    assert [
        (row["id"], row["bell_preparation"], row["normal"], row["hard"])
        for row in report["controls"]
    ] == [
        ("reference_order", True, "pass", "pass"),
        ("mirrored_preparation", True, "fail", "fail"),
        ("preparation_with_initial_z", True, "fail", "fail"),
        ("global_phase_reference", True, "pass", "pass"),
        ("identity_wrong_state", False, "fail", "fail"),
    ]
    assert all(row["unitary_error"] < 1e-14 for row in report["controls"])
    assert all(row["sdk_matrix_error"] < 1e-14 for row in report["controls"])
    assert all(len(row["judged_matrix"]) == 4 for row in report["controls"])
    assert module.verify(report, cache) is True
    changed = dict(report, controls=report["controls"][:-1])
    with pytest.raises(ValueError, match="exact recreation"):
        module.verify(changed, cache)
    normal = load_suite("normal", cache)[12]
    hard = load_suite("hard", cache)[12]
    with pytest.raises(ValueError, match="exact pinned task 12"):
        module.probe(
            normal.model_copy(update={"upstream_test": "raise RuntimeError('untrusted')"}), hard
        )

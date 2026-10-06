"""Pinned task-110 tolerance evidence is internally consistent and reproducible."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from graybench.datasets import load_suite

ROOT = Path(__file__).resolve().parents[2]
WORKLOAD = ROOT / "docs/reliability-evidence/task110_tolerance_workload.py"
REPORT = ROOT / "docs/reliability-evidence/artifacts/task110-tolerance-2026-10-06/report.json"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
PINNED_TESTS = {
    "normal": (
        "da6ad9bb17b1f7437d7b709e9905b6e8e7fa82c282b76bd25466e89f3cc337d1",
        "5b2ac0775c45c9f40549af327ee0dfbac62f9744aae0cc22f54dc23be6e86e0f",
    ),
    "hard": (
        "7ff2acaded27c33c081fa11fd44fa7ec3b9413b77cc17e1c6eba28f2ee05dbe1",
        "041ac0cbb9f453434a4458d56f61cf6f028ae827dfab6c441ec57fae0f8a44a9",
    ),
}


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_task110_tolerance_matches_exact_pinned_tests():
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    for suite, (task_digest, test_digest) in PINNED_TESTS.items():
        task = load_suite(suite, cache)[110]
        assert task.digest == task_digest
        assert hashlib.sha256(task.upstream_test.encode()).hexdigest() == test_digest
        assert "random_clifford(5)" in task.upstream_test
        assert "candidate(qc_comp, 10)" in task.upstream_test
        assert "rtol = 0.4, atol = 0.4" in task.upstream_test
        assert "len(can_circ_list)" not in task.upstream_test


def test_task110_tolerance_report_has_complete_fixed_seed_population():
    report = json.loads(REPORT.read_bytes())
    assert report["workload_sha256"] == hashlib.sha256(WORKLOAD.read_bytes()).hexdigest()
    assert report["image"] == IMAGE
    assert report["qubits"] == 5
    assert report["reference_seed"] == 1
    assert [case["candidate_seed"] for case in report["cases"]] == list(range(2, 102))
    assert report["counts"] == {
        "same_clifford": 0,
        "strict_operator_equiv": 0,
        "pinned_test_operator_equiv": 98,
    }
    assert all(
        not case["same_clifford"] and not case["strict_operator_equiv"] for case in report["cases"]
    )
    assert [
        case["candidate_seed"] for case in report["cases"] if not case["pinned_test_operator_equiv"]
    ] == [86, 92]


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_task110_tolerance_report_reproduces_inside_pinned_image():
    assert os.environ["GRAYBENCH_TEST_IMAGE"] == IMAGE
    actual = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--tmpfs",
            "/tmp:rw,nosuid,size=64m",
            "--mount",
            f"type=bind,source={WORKLOAD},target=/probe.py,readonly",
            "--entrypoint",
            "python",
            IMAGE,
            "/probe.py",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert json.loads(actual.stdout) == json.loads(REPORT.read_bytes())

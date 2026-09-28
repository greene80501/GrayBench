"""The committed runtime fingerprint must be independently checkable in Docker."""

import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

RUNTIME = Path(__file__).parents[1] / "runtime"


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Needs pinned image")
def test_pinned_runtime_matches_committed_package_fingerprint():
    result = subprocess.run(
        [
            sys.executable,
            str(RUNTIME / "verify_runtime.py"),
            os.environ["GRAYBENCH_TEST_IMAGE"],
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "matching_package_fingerprint"
    assert report["package_counts"] == {"debian": 157, "python": 96}


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Needs pinned image")
def test_runtime_verifier_rejects_changed_expected_fingerprint(tmp_path):
    manifest = json.loads((RUNTIME / "package-fingerprint.json").read_text())
    manifest["python_packages_sha256"] = "0" * 64
    altered = tmp_path / "altered.json"
    altered.write_text(json.dumps(manifest))
    result = subprocess.run(
        [
            sys.executable,
            str(RUNTIME / "verify_runtime.py"),
            os.environ["GRAYBENCH_TEST_IMAGE"],
            "--fingerprint",
            str(altered),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["status"] == "package_fingerprint_mismatch"


def test_runtime_verifier_rejects_mutable_image_tag():
    result = subprocess.run(
        [sys.executable, str(RUNTIME / "verify_runtime.py"), "graybench-evaluator:latest"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "runtime_probe_failed"


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Needs pinned image")
def test_bell_smoke_rejects_wrong_state_with_python_optimization():
    smoke = runpy.run_path(str(RUNTIME / "verify_runtime.py"))["SMOKE"]
    wrong = smoke.replace(
        "expected = numpy.array([2**-0.5, 0, 0, 2**-0.5])",
        "expected = numpy.zeros(4)",
    )
    assert wrong != smoke
    result = subprocess.run(
        [
            os.environ.get("GRAYBENCH_DOCKER", "docker"),
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            os.environ["GRAYBENCH_TEST_IMAGE"],
            "python",
            "-O",
            "-c",
            wrong,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "Bell-state smoke check failed" in result.stderr

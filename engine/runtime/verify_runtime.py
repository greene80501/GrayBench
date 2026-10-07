"""Check a local evaluator image against the committed package inventory.

This verifies installed versions and a small quantum operation, not image-byte
identity, build provenance, or the semantic adequacy of benchmark tasks.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

DEFAULT_FINGERPRINT = Path(__file__).with_name("package-fingerprint.json")
SMOKE = """import json, sys, numpy, qiskit, scipy
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
circuit = QuantumCircuit(2)
circuit.h(0)
circuit.cx(0, 1)
actual = Statevector.from_instruction(circuit).data
expected = numpy.array([2**-0.5, 0, 0, 2**-0.5])
if not numpy.allclose(actual, expected, rtol=0, atol=1e-12):
    raise RuntimeError("Bell-state smoke check failed")
print(json.dumps({"python_version": sys.version.split()[0],
                  "qiskit_version": qiskit.__version__,
                  "numpy_version": numpy.__version__,
                  "scipy_version": scipy.__version__}, sort_keys=True))
"""


def _run(command: list[str], *, timeout: int = 120) -> str:
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=timeout)
    return result.stdout.strip()


def _package_fingerprint(output: str) -> tuple[int, str]:
    lines = sorted(output.splitlines())
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    return len(lines), hashlib.sha256(payload).hexdigest()


def inspect(image: str, docker: str, fingerprint: Path) -> dict:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ValueError("Use an immutable local sha256 image reference")
    expected_bytes = fingerprint.read_bytes()
    expected = json.loads(expected_bytes)
    if expected.get("schema_version") != "1" or expected.get("platform") != "linux/amd64":
        raise ValueError("Unsupported runtime fingerprint")
    image_info = _run(
        [
            docker,
            "image",
            "inspect",
            "--platform",
            "linux/amd64",
            image,
            "--format",
            "{{.Id}} {{.Os}}/{{.Architecture}}",
        ]
    )
    image_id, platform = image_info.split()
    if platform != "linux/amd64" or not image_id.startswith("sha256:"):
        raise ValueError("Evaluator image is not Linux/amd64")

    def in_container(*command: str) -> str:
        return _run(
            [
                docker,
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
                image,
                *command,
            ]
        )

    python_count, python_digest = _package_fingerprint(
        in_container("python", "-m", "pip", "freeze")
    )
    debian_count, debian_digest = _package_fingerprint(in_container("dpkg-query", "-W"))
    versions = json.loads(in_container("python", "-c", SMOKE))
    observed = {
        "platform": platform,
        **versions,
        "python_package_count": python_count,
        "python_packages_sha256": python_digest,
        "debian_package_count": debian_count,
        "debian_packages_sha256": debian_digest,
    }
    mismatches = sorted(key for key, value in observed.items() if expected.get(key) != value)
    return {
        "status": "package_fingerprint_mismatch" if mismatches else "matching_package_fingerprint",
        "image_ref": image,
        "platform_image_id": image_id,
        "fingerprint_file_sha256": hashlib.sha256(expected_bytes).hexdigest(),
        "package_counts": {"python": python_count, "debian": debian_count},
        "observed": observed,
        "mismatched_fields": mismatches,
        "byte_identical_to_historical_image": "not_established",
        "publication_eligible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--fingerprint", type=Path, default=DEFAULT_FINGERPRINT)
    args = parser.parse_args()
    try:
        report = inspect(args.image, args.docker, args.fingerprint)
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        error = {"status": "runtime_probe_failed", "error": type(exc).__name__}
        if isinstance(exc, subprocess.CalledProcessError):
            error["return_code"] = exc.returncode
            error["stderr_tail"] = (exc.stderr or "")[-1000:]
        print(json.dumps(error))
        raise SystemExit(2) from exc
    print(json.dumps(report, sort_keys=True))
    if report["mismatched_fields"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

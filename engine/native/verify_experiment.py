"""Record bounded native experiment checks against one immutable Docker image."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--docker", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native = Path(__file__).resolve().parent
    image = subprocess.run(
        [args.docker, "image", "inspect", args.image, "--format", "{{.Id}}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    scripts = (
        "check_registered_factory.py",
        "check_registered_storage.py",
        "check_capsule_metadata.py",
        "check_reentrant_cleanup.py",
    )
    cases = []
    for script in scripts:
        command = [
            args.docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "2g",
            "--cpus",
            "1",
            "--mount",
            f"type=bind,source={native / 'tests'},target=/checks,readonly",
            image,
            "python",
            f"/checks/{script}",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        cases.append(
            {
                "script": script,
                "script_sha256": digest(native / "tests" / script),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
    sanitizer = subprocess.run(
        [
            args.docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "2g",
            "--cpus",
            "1",
            "--tmpfs",
            "/tmp:rw,exec,size=128m",
            "--mount",
            f"type=bind,source={native},target=/native,readonly",
            image,
            "sh",
            "-c",
            "gcc -shared -fPIC -g -O1 -fsanitize=address "
            "-I/usr/local/include/python3.12 "
            "-I/usr/local/lib/python3.12/site-packages/numpy/_core/include "
            "/native/tests/registry_harness.c -o /tmp/_registry_test.so && "
            "LD_PRELOAD=$(gcc -print-file-name=libasan.so) "
            "ASAN_OPTIONS=detect_leaks=0 "
            "python /native/tests/check_registry_reentry_asan.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    cases.append(
        {
            "script": "check_registry_reentry_asan.py",
            "script_sha256": digest(native / "tests" / "check_registry_reentry_asan.py"),
            "harness_sha256": digest(native / "tests" / "registry_harness.c"),
            "returncode": sanitizer.returncode,
            "stdout": sanitizer.stdout,
            "stderr": sanitizer.stderr,
        }
    )
    evidence = {
        "kind": "experimental_native_storage_v1",
        "image": image,
        "header_sha256": digest(native / "registered_storage.h"),
        "patch_sha256": digest(native / "patch_scipy.py"),
        "cases": cases,
        "scope": "standalone native checks only; no graph or benchmark admission",
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"image": image, "returncodes": [case["returncode"] for case in cases]}))
    if any(case["returncode"] != 0 for case in cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Disposable Docker execution: no network, credentials, or user-directory mounts."""

import subprocess
import uuid
from graybench.execution.process import run_bounded

DEFAULT_IMAGE = "graybench-evaluator:2.0"


def image_id(image=DEFAULT_IMAGE):
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(
            "Docker evaluator unavailable. Build the supplied Dockerfile first."
        ) from error
    return result.stdout.strip()


def command(image, directory, name):
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "4g",
        "--cpus",
        "1",
        "--user",
        "65534:65534",
        "--tmpfs",
        "/tmp:rw,nosuid,size=256m",
        "--mount",
        f"type=bind,source={directory.resolve()},target=/input,readonly",
        "--workdir",
        "/tmp",
        "--env",
        "HOME=/tmp",
        "--env",
        "MPLCONFIGDIR=/tmp/matplotlib",
        "--env",
        "MPLBACKEND=Agg",
        "--env",
        "PYTHONHASHSEED=0",
        "--env",
        "OMP_NUM_THREADS=1",
        image,
        "python",
        "/input/test_harness.py",
    ]


def execute(image, directory, timeout, max_output_bytes=1024 * 1024):
    name = "graybench-" + uuid.uuid4().hex
    try:
        return run_bounded(command(image, directory, name), timeout=timeout, limit=max_output_bytes)
    finally:
        # The CLI may time out while a container still runs. Remove only our own unique container.
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30)

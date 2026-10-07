"""Relevant execution provenance without environment variables, credentials, or user files."""

import hashlib
import importlib.metadata
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from graybench.identity import identity


def source_manifest() -> dict:
    root = Path(__file__).parent
    files = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*.py"))
    }
    return {"files": files, "digest": identity(files)}


def environment() -> dict:
    result = {
        "observed_at": datetime.now(UTC).isoformat(),
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "build": list(platform.python_build()),
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "cpu": {"description": platform.processor() or None, "logical_count": os.cpu_count()},
        "packages": dict(
            sorted(
                (d.metadata["Name"], d.version)
                for d in importlib.metadata.distributions()
                if d.metadata["Name"]
            )
        ),
        "source": source_manifest(),
        "gpu": {"status": "unavailable"},
        "executable_architecture_bits": 64 if sys.maxsize > 2**32 else 32,
    }
    try:
        query = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,uuid,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        result["gpu"] = {
            "status": "observed",
            "source": "nvidia-smi",
            "fields": ["name", "uuid", "driver_version", "memory_total_mib"],
            "rows": [line.strip() for line in query.stdout.splitlines()],
        }
    except (OSError, subprocess.SubprocessError):
        pass
    return result

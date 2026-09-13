"""Resource-limited independent semantic judge. Host forwards data without decoding Qiskit.

Candidate execution and judgment use disjoint mounts, processes and output channels. A pass
can originate only from the trusted judge process, never from candidate stdout or metadata.
"""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from graybench.identity import canonical, identity

JUDGE_FILES = (
    "judge_process.py",
    "oracles.py",
    "value_wire.py",
    "circuit_wire.py",
    "scientific_wire.py",
    "symbolic_wire.py",
)
ORACLES = frozenset({"task20-ghz-state-v1"})


@dataclass(frozen=True)
class Judgment:
    outcome: str
    judge_digest: str
    evidence: dict


class ProtectedJudge:
    def __init__(
        self,
        *,
        image: str,
        docker: str = "docker",
        timeout: float = 120,
        output_limit: int = 1024 * 1024,
    ):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("Judge requires an immutable runtime image")
        if timeout <= 0 or output_limit < 1024:
            raise ValueError("Invalid judge resource limits")
        self.image, self.docker, self.timeout, self.limit = image, docker, timeout, output_limit

    def manifest(self, oracle: str) -> dict:
        if oracle not in ORACLES:
            raise ValueError("Unknown trusted oracle")
        root = Path(__file__).parent
        files = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in JUDGE_FILES
        }
        files["judge.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        return {
            "oracle": oracle,
            "files": files,
            "image": self.image,
            "timeout": self.timeout,
            "output_limit": self.limit,
            "memory_bytes": 4 * 1024**3,
            "cpus": 1,
            "protocol": 1,
        }

    def evaluate(self, value: object, *, oracle: str) -> Judgment:
        manifest = self.manifest(oracle)
        digest = identity(manifest)
        try:
            payload = canonical({"oracle": oracle, "value": value})
        except (TypeError, ValueError, RecursionError) as exc:
            return Judgment(
                "candidate_error",
                digest,
                {"reason": "non-JSON wire value", "exception": type(exc).__name__},
            )
        if len(payload) > self.limit:
            return Judgment("candidate_error", digest, {"reason": "wire input exceeds limit"})
        name = "graybench-judge-" + uuid.uuid4().hex
        buffers = [bytearray(), bytearray()]
        exceeded = threading.Event()
        process = None
        readers = []
        with tempfile.TemporaryDirectory(prefix="graybench-judge-") as directory:
            root = Path(directory)
            (root / "input.json").write_bytes(payload)
            for filename in JUDGE_FILES:
                shutil.copyfile(Path(__file__).with_name(filename), root / filename)
            args = [
                self.docker,
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
                f"type=bind,source={root},target=/judge,readonly",
                "--workdir",
                "/tmp",
                "--env",
                "HOME=/tmp",
                "--env",
                "OMP_NUM_THREADS=1",
                self.image,
                "python",
                "-u",
                "/judge/judge_process.py",
            ]

            def drain(stream, buffer):
                try:
                    while chunk := stream.read(8192):
                        remaining = max(0, self.limit - len(buffer))
                        buffer.extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            exceeded.set()
                            process.kill()
                            return
                finally:
                    stream.close()

            try:
                process = subprocess.Popen(
                    args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                readers = [
                    threading.Thread(target=drain, args=(stream, buffer), daemon=True)
                    for stream, buffer in zip(
                        (process.stdout, process.stderr), buffers, strict=True
                    )
                ]
                for reader in readers:
                    reader.start()
                process.wait(timeout=self.timeout)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return Judgment(
                    "infrastructure_error",
                    digest,
                    {"reason": "judge execution failed", "exception": type(exc).__name__},
                )
            finally:
                # Kill both container and CLI on timeout or output overflow.
                try:
                    subprocess.run(
                        [self.docker, "rm", "--force", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                for reader in readers:
                    reader.join(timeout=2)
            if exceeded.is_set() or process.returncode != 0:
                return Judgment(
                    "infrastructure_error",
                    digest,
                    {
                        "reason": "judge failed or exceeded output limit",
                        "exit_code": process.returncode,
                        "stderr": buffers[1].decode("utf-8", errors="replace"),
                    },
                )
            try:
                result = json.loads(buffers[0])
                if (
                    set(result) != {"protocol", "oracle", "outcome", "evidence"}
                    or result["protocol"] != 1
                    or result["oracle"] != oracle
                    or result["outcome"] not in {"pass", "fail", "candidate_error"}
                    or type(result["evidence"]) is not dict
                ):
                    raise ValueError("Invalid trusted judge envelope")
            except (ValueError, TypeError) as exc:
                return Judgment(
                    "infrastructure_error",
                    digest,
                    {"reason": "judge protocol failure", "detail": str(exc)},
                )
            return Judgment(
                result["outcome"],
                digest,
                {
                    **result["evidence"],
                    "manifest": manifest,
                    "input_sha256": hashlib.sha256(payload).hexdigest(),
                },
            )

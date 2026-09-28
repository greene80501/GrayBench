"""Host supervisor for native same-process pinned QHE reproduction.

Candidate and pinned test share an interpreter by design. This preserves Python/Qiskit
semantics but cannot certify resistance to deliberate same-process test tampering.
"""

import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from graybench.datasets import JudgeTask
from graybench.identity import canonical, identity
from graybench.judge import Judgment
from graybench.native_assembly import native_payload
from graybench.native_cohort import NativeCohort, task_key, validate_native_cohort

WORKER = Path(__file__).with_name("native_worker.py")
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_RESULT_BYTES = 16 * 1024


def native_command(
    *,
    docker: str,
    image: str,
    name: str,
    mount_dir: Path,
    result_dir: Path,
    memory_bytes: int,
    cpus: float,
    pids_limit: int,
    tmpfs_bytes: int,
) -> list[str]:
    """Construct one isolated Docker invocation without credential or user mounts."""
    return [
        docker,
        "run",
        "-i",
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
        str(pids_limit),
        "--memory",
        str(memory_bytes),
        "--memory-swap",
        str(memory_bytes),
        "--cpus",
        str(cpus),
        "--user",
        "65534:65534",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,mode=1777,size={tmpfs_bytes}",
        "--mount",
        f"type=bind,source={mount_dir.resolve()},target=/native,readonly",
        "--mount",
        f"type=bind,source={result_dir.resolve()},target=/result",
        "--workdir",
        "/tmp",
        "--env",
        "HOME=/tmp",
        "--env",
        "OMP_NUM_THREADS=1",
        image,
        "python",
        "-u",
        "/native/native_worker.py",
        "/result/result.json",
    ]


class NativeJudge:
    track = "qhe-pinned-native-v1"

    def __init__(
        self,
        cohort: NativeCohort,
        tasks: tuple[JudgeTask, ...],
        *,
        cache: Path,
        docker: str = "docker",
        timeout: float = 120,
        output_limit: int = 1024 * 1024,
        memory_bytes: int = 2 * 1024**3,
        cpus: float = 2,
        pids_limit: int = 64,
        tmpfs_bytes: int = 64 * 1024**2,
    ):
        if (
            not math.isfinite(timeout)
            or timeout <= 0
            or not math.isfinite(cpus)
            or cpus <= 0
            or type(output_limit) is not int
            or not 1024 <= output_limit <= 16 * 1024**2
            or type(memory_bytes) is not int
            or memory_bytes < 128 * 1024**2
            or type(pids_limit) is not int
            or pids_limit < 2
            or type(tmpfs_bytes) is not int
            or tmpfs_bytes < 1024**2
        ):
            raise ValueError("Invalid native resource limit")
        self.cohort, self.tasks, self.cache = cohort, tasks, cache
        self.image, self.extraction = cohort.image, cohort.extraction
        self.docker, self.timeout, self.output_limit = docker, timeout, output_limit
        self.memory_bytes, self.cpus = memory_bytes, cpus
        self.pids_limit, self.tmpfs_bytes = pids_limit, tmpfs_bytes

    def configuration(self, task: JudgeTask) -> tuple[dict, dict]:
        key = task_key(task)
        if self.cohort.task_digests.get(key) != task.digest:
            raise ValueError("Native task differs from frozen cohort")
        manifest = {
            "track": self.track,
            "suite": self.cohort.suite,
            "population": self.cohort.population,
            "cohort_digest": self.cohort.digest,
            "task_key": key,
            "task_digest": task.digest,
            "image": self.cohort.image,
            "extraction": self.cohort.extraction,
            "worker_sha256": hashlib.sha256(WORKER.read_bytes()).hexdigest(),
            "assembly_sha256": hashlib.sha256(
                Path(__file__).with_name("native_assembly.py").read_bytes()
            ).hexdigest(),
            "supervisor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "timeout_seconds": self.timeout,
            "output_limit": self.output_limit,
            "payload_limit": MAX_PAYLOAD_BYTES,
            "result_limit": MAX_RESULT_BYTES,
            "memory_bytes": self.memory_bytes,
            "cpus": self.cpus,
            "pids_limit": self.pids_limit,
            "tmpfs_bytes": self.tmpfs_bytes,
            "result_channel": "isolated-ephemeral-host-bind-v1",
            "release_eligible": False,
            "integrity_limit": "same_process_candidate_can_inspect_or_tamper_with_test",
        }
        if self.cohort.exception_policy != "conservative_unattributed_v1":
            manifest["exception_policy"] = self.cohort.exception_policy
        return {}, manifest

    def evaluate(self, task: JudgeTask, completion: str) -> Judgment:
        _, manifest = self.configuration(task)
        digest = identity(manifest)
        validate_native_cohort(self.cohort, self.tasks, cache=self.cache)
        payload = native_payload(task, completion, self.cohort.extraction)
        if self.cohort.exception_policy != "conservative_unattributed_v1":
            payload["exception_policy"] = self.cohort.exception_policy
        evidence = {
            "manifest": manifest,
            "completion_sha256": payload["completion_sha256"],
            "extraction_method": payload["extraction_method"],
        }
        if "completion_digest_encoding" in payload:
            evidence["completion_digest_encoding"] = payload["completion_digest_encoding"]
        if "extraction_error" in payload:
            return Judgment(
                "candidate_error", digest, {**evidence, "detail": payload["extraction_error"]}
            )
        evidence["code_sha256"] = payload["code_sha256"]
        wire = canonical(payload)
        if len(wire) > MAX_PAYLOAD_BYTES:
            return Judgment("candidate_error", digest, {**evidence, "reason": "payload_limit"})
        return self._execute(wire, digest, evidence)

    def _execute(self, wire: bytes, digest: str, evidence: dict) -> Judgment:
        name = "graybench-native-" + uuid.uuid4().hex
        output = [bytearray(), bytearray()]
        total = [0]
        lock = threading.Lock()
        exceeded = threading.Event()
        process = None
        readers = []
        writer = None
        timed_out = False
        with tempfile.TemporaryDirectory(prefix="graybench-native-") as directory:
            root = Path(directory)
            source_dir, result_dir = root / "source", root / "result"
            source_dir.mkdir()
            result_dir.mkdir()
            shutil.copyfile(WORKER, source_dir / "native_worker.py")
            command = native_command(
                docker=self.docker,
                image=self.cohort.image,
                name=name,
                mount_dir=source_dir,
                result_dir=result_dir,
                memory_bytes=self.memory_bytes,
                cpus=self.cpus,
                pids_limit=self.pids_limit,
                tmpfs_bytes=self.tmpfs_bytes,
            )

            def drain(stream, buffer):
                try:
                    while chunk := stream.read(8192):
                        with lock:
                            remaining = max(0, self.output_limit - total[0])
                            taken = chunk[:remaining]
                            buffer.extend(taken)
                            total[0] += len(taken)
                            overflow = len(chunk) > remaining
                        if overflow:
                            exceeded.set()
                            process.kill()
                            return
                finally:
                    stream.close()

            def send():
                try:
                    process.stdin.write(wire)
                    process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    process.stdin.close()

            try:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                readers = [
                    threading.Thread(target=drain, args=(stream, buffer), daemon=True)
                    for stream, buffer in zip((process.stdout, process.stderr), output, strict=True)
                ]
                for reader in readers:
                    reader.start()
                writer = threading.Thread(target=send, daemon=True)
                writer.start()
                process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            except OSError as exc:
                return Judgment(
                    "infrastructure_error",
                    digest,
                    {**evidence, "reason": "docker_launch", "exception": type(exc).__name__},
                )
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                if writer is not None:
                    writer.join(timeout=2)
                for reader in readers:
                    reader.join(timeout=2)

            evidence = {
                **evidence,
                "exit_code": process.returncode,
                "stdout": output[0].decode("utf-8", errors="replace"),
                "stderr": output[1].decode("utf-8", errors="replace"),
                "output_bytes": total[0],
            }
            try:
                if timed_out:
                    return Judgment("timeout", digest, {**evidence, "reason": "native_timeout"})
                if exceeded.is_set():
                    return Judgment(
                        "candidate_error", digest, {**evidence, "reason": "native_output_limit"}
                    )
                if process.returncode != 0:
                    return Judgment(
                        "infrastructure_error",
                        digest,
                        {**evidence, "reason": "native_process_nonzero"},
                    )
                return self._result(result_dir / "result.json", digest, evidence)
            finally:
                try:
                    subprocess.run(
                        [self.docker, "rm", "--force", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass

    def _result(self, path: Path, digest: str, evidence: dict) -> Judgment:
        try:
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RESULT_BYTES:
                raise ValueError("Native result is not one bounded regular file")
            data = path.read_bytes()
            if len(data) != info.st_size or len(data) > MAX_RESULT_BYTES:
                raise ValueError("Native result size changed after container exit")
            result = json.loads(data)
            if (
                not isinstance(result, dict)
                or result.get("completed") is not True
                or result.get("status")
                not in {"pass", "fail", "candidate_error", "infrastructure_error"}
                or not isinstance(result.get("phase"), str)
                or set(result) - {"completed", "status", "phase", "exception_type", "detail"}
            ):
                raise ValueError("Malformed native completion envelope")
            return Judgment(
                result["status"],
                digest,
                {
                    **evidence,
                    "worker_result": result,
                    "result_artifact": {
                        "name": "result.json",
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "capture": "isolated-ephemeral-host-bind-v1",
                    },
                },
            )
        except FileNotFoundError:
            return Judgment(
                "candidate_error", digest, {**evidence, "reason": "missing_native_completion"}
            )
        except (OSError, ValueError, TypeError) as exc:
            return Judgment(
                "infrastructure_error",
                digest,
                {**evidence, "reason": "native_result_unverified", "exception": type(exc).__name__},
            )

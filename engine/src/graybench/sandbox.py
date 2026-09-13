"""Candidate-only Docker process with an untrusted, bounded JSON result channel.

The initial codec supports plain values. Unsupported interfaces block eligibility and
publication until implemented and validated; there is no same-process judge fallback.
"""

import json
import math
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path


class CandidateError(RuntimeError):
    pass


class UnsupportedInterface(RuntimeError):
    pass


def decode(value, depth=0, budget=None):
    """No imports, executable names, pickle, eval, or candidate-supplied constructors."""
    if budget is None:
        budget = [100_000]
    budget[0] -= 1
    if depth > 32 or budget[0] < 0:
        raise CandidateError("Result exceeds structural limit")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is not dict or set(value) != {"kind", "items"}:
        raise CandidateError("Invalid result wire type")
    if type(value["items"]) is not list:
        raise CandidateError("Invalid result items")
    if value["kind"] in ("list", "tuple"):
        items = [decode(x, depth + 1, budget) for x in value["items"]]
        return items if value["kind"] == "list" else tuple(items)
    if value["kind"] == "dict":
        result = {}
        for pair in value["items"]:
            if type(pair) is not list or len(pair) != 2:
                raise CandidateError("Invalid dictionary pair")
            key = decode(pair[0], depth + 1, budget)
            try:
                if key in result:
                    raise CandidateError("Duplicate dictionary key")
                result[key] = decode(pair[1], depth + 1, budget)
            except TypeError as exc:
                raise CandidateError("Unhashable dictionary key") from exc
        return result
    raise CandidateError("Unknown result kind")


class Candidate:
    def __init__(
        self,
        code: str,
        *,
        image: str,
        timeout: float = 120,
        output_limit: int = 1024 * 1024,
        docker: str = "docker",
        public_prefix: str = "",
    ):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("Candidate runtime must use an immutable local image digest")
        self.name = "graybench-v3-" + uuid.uuid4().hex
        self.docker = docker
        self.timeout = timeout
        self.limit = output_limit
        self.sequence = 0
        self.directory = tempfile.TemporaryDirectory(prefix="graybench-v3-")
        self.process = None
        self.closed = False
        self.readers = []
        self.stderr = bytearray()
        self.messages = queue.Queue(maxsize=2)
        self.stopping = threading.Event()
        self.exceeded = threading.Event()
        directory = Path(self.directory.name)
        (directory / "candidate.py").write_text(code, encoding="utf-8")
        if public_prefix:
            (directory / "public_prefix.py").write_text(public_prefix, encoding="utf-8")
        shutil.copyfile(Path(__file__).with_name("worker.py"), directory / "worker.py")
        args = [
            docker,
            "run",
            "--rm",
            "-i",
            "--name",
            self.name,
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
            f"type=bind,source={directory},target=/input,readonly",
            "--workdir",
            "/tmp",
            "--env",
            "HOME=/tmp",
            "--env",
            "MPLCONFIGDIR=/tmp/matplotlib",
            "--env",
            "MPLBACKEND=Agg",
            "--env",
            "OMP_NUM_THREADS=1",
            image,
            "python",
            "-u",
            "/input/worker.py",
        ]
        try:
            self.process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            self.readers = [
                threading.Thread(target=self._read_stdout, daemon=True),
                threading.Thread(target=self._read_stderr, daemon=True),
            ]
            for reader in self.readers:
                reader.start()
            self.deadline = time.monotonic() + timeout
            if self._receive() != {"protocol": 1, "ready": True}:
                raise CandidateError("Candidate did not initialize the value protocol")
        except BaseException:
            self.close()
            raise

    def _queue(self, item):
        while not self.stopping.is_set():
            try:
                self.messages.put(item, timeout=0.1)
                return
            except queue.Full:
                continue

    def _read_stdout(self):
        total = 0
        while not self.stopping.is_set():
            line = self.process.stdout.readline(self.limit + 1)
            total += len(line)
            if total > self.limit:
                self.exceeded.set()
                self._queue(CandidateError("Candidate output limit exceeded"))
                return
            if not line:
                self._queue(CandidateError("Candidate exited before returning a value"))
                return
            self._queue(line)

    def _read_stderr(self):
        while not self.stopping.is_set():
            chunk = self.process.stderr.read(8192)
            if not chunk:
                return
            remaining = self.limit - len(self.stderr)
            self.stderr.extend(chunk[:remaining])
            if len(chunk) > remaining:
                self.exceeded.set()
                self._queue(CandidateError("Candidate diagnostic output limit exceeded"))
                return

    def _receive(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Candidate sample time limit exceeded")
        try:
            message = self.messages.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError("Candidate sample time limit exceeded") from exc
        if self.exceeded.is_set():
            raise CandidateError("Candidate output limit exceeded")
        if isinstance(message, Exception):
            raise message
        try:
            return json.loads(message)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise CandidateError("Candidate output is not a result message") from exc

    def call(self, entry_point: str, *args, **kwargs):
        # Input codecs are currently restricted to plain JSON; no implicit str conversion.
        self.sequence += 1
        request = (
            json.dumps(
                {
                    "entry_point": entry_point,
                    "args": args,
                    "kwargs": kwargs,
                    "sequence": self.sequence,
                },
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        if len(request) > self.limit:
            raise UnsupportedInterface("Call input exceeds transport limit")
        write_errors = []

        def send():
            try:
                self.process.stdin.write(request)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                write_errors.append(exc)

        sender = threading.Thread(target=send, daemon=True)
        self.readers.append(sender)
        sender.start()
        sender.join(timeout=max(0, self.deadline - time.monotonic()))
        if sender.is_alive():
            raise TimeoutError("Candidate did not accept call input before the deadline")
        if write_errors:
            raise CandidateError("Candidate closed its input") from write_errors[0]
        response = self._receive()
        if type(response) is not dict or response.get("protocol") != 1:
            raise CandidateError("Invalid candidate value envelope")
        if type(response.get("sequence")) is not int or response["sequence"] != self.sequence:
            raise CandidateError("Unmatched candidate response")
        if set(response) == {"protocol", "sequence", "error", "detail"}:
            # Worker errors are untrusted diagnostics, never proof of an infrastructure defect.
            raise CandidateError(str(response["error"]) + ": " + str(response["detail"]))
        if set(response) != {"protocol", "sequence", "value"}:
            raise CandidateError("Unexpected candidate envelope fields")
        return decode(response["value"])

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stopping.set()
        if self.process is not None:
            try:
                subprocess.run(
                    [self.docker, "rm", "--force", self.name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=10)
            for reader in self.readers:
                reader.join(timeout=2)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()
        self.directory.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

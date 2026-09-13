"""Candidate-only Docker process with an untrusted, bounded JSON result channel.

The current codec supports plain values and numeric circuits. Unsupported interfaces block
eligibility and publication until validated; there is no same-process judge fallback.
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
from dataclasses import dataclass
from pathlib import Path

from graybench.container_control import ContainerControl
from graybench.value_wire import encode


class CandidateError(RuntimeError):
    pass


class CandidateInterfaceError(CandidateError):
    """Untrusted codec diagnostic requiring adjudication, never a scored verdict."""


class UnsupportedInterface(RuntimeError):
    pass


def decode(value, depth=0, budget=None):
    from graybench.value_wire import decode as decode_value

    try:
        return decode_value(value, depth, budget)
    except (ValueError, TypeError) as exc:
        raise CandidateError(str(exc)) from exc


@dataclass(frozen=True)
class CallResult:
    value: object
    args_after: tuple
    kwargs_after: dict


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
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Candidate timeout must be finite and positive")
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
        self.active_seconds = 0.0
        self.active_started = None
        self.paused = False
        self.control = None
        directory = Path(self.directory.name)
        (directory / "candidate.py").write_text(code, encoding="utf-8")
        if public_prefix:
            (directory / "public_prefix.py").write_text(public_prefix, encoding="utf-8")
        shutil.copyfile(Path(__file__).with_name("worker.py"), directory / "worker.py")
        shutil.copyfile(Path(__file__).with_name("circuit_wire.py"), directory / "circuit_wire.py")
        shutil.copyfile(Path(__file__).with_name("value_wire.py"), directory / "value_wire.py")
        shutil.copyfile(
            Path(__file__).with_name("scientific_wire.py"), directory / "scientific_wire.py"
        )
        shutil.copyfile(
            Path(__file__).with_name("symbolic_wire.py"), directory / "symbolic_wire.py"
        )
        shutil.copyfile(
            Path(__file__).with_name("preparation_wire.py"), directory / "preparation_wire.py"
        )
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
            self.control = ContainerControl(docker)
            self.active_started = time.monotonic()
            self.deadline = self.active_started + timeout
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
            if self._receive() != {"protocol": 3, "ready": True}:
                raise CandidateError("Candidate did not initialize the value protocol")
            self._pause()
        except BaseException:
            self.close()
            raise

    def _control(self, operation):
        """Host-authoritative container freeze; failures are infrastructure errors."""
        try:
            if operation == "pause":
                self.control.pause(self.name)
            elif operation == "unpause":
                self.control.unpause(self.name)
            else:
                raise ValueError("Unsupported lifecycle operation")
        except Exception as exc:
            raise RuntimeError("Candidate container lifecycle operation failed") from exc

    def _pause(self):
        if self.paused:
            return
        self._control("pause")
        self.paused = True
        self.active_seconds += time.monotonic() - self.active_started
        self.active_started = None
        if self.active_seconds >= self.timeout:
            raise TimeoutError("Candidate sample active-time limit exceeded")

    def _resume(self):
        if self.closed or not self.paused:
            raise RuntimeError("Candidate is not available for a new call")
        remaining = self.timeout - self.active_seconds
        if remaining <= 0:
            raise TimeoutError("Candidate sample active-time limit exceeded")
        # Include lifecycle overhead conservatively; no running interval is unmetered.
        self.active_started = time.monotonic()
        self.deadline = self.active_started + remaining
        self._control("unpause")
        self.paused = False

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
        result = self.call_with_updates(entry_point, *args, **kwargs)
        if encode(args) != encode(result.args_after) or encode(kwargs) != encode(
            result.kwargs_after
        ):
            raise UnsupportedInterface(
                "Input mutation requires the explicit call_with_updates interface"
            )
        return result.value

    def call_with_updates(self, entry_point: str, *args, **kwargs):
        response = self.call_wire(entry_point, *args, **kwargs)
        args_after, kwargs_after = decode(response["args_after"]), decode(response["kwargs_after"])
        if (
            type(args_after) is not tuple
            or len(args_after) != len(args)
            or type(kwargs_after) is not dict
            or set(kwargs_after) != set(kwargs)
        ):
            raise CandidateError("Invalid call argument snapshot")
        return CallResult(decode(response["value"]), args_after, kwargs_after)

    def call_wire(self, entry_point: str, *args, **kwargs):
        """Return untrusted wire data without reconstructing candidate objects on the host."""
        return self.call_encoded(entry_point, encode(args), encode(kwargs))

    def call_encoded(self, entry_point: str, args_wire, kwargs_wire):
        """Forward a trusted judge's typed inputs without host object reconstruction."""
        self.sequence += 1
        request = (
            json.dumps(
                {
                    "entry_point": entry_point,
                    "args": args_wire,
                    "kwargs": kwargs_wire,
                    "sequence": self.sequence,
                },
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        if len(request) > self.limit:
            raise UnsupportedInterface("Call input exceeds transport limit")
        try:
            self._resume()
            response = self._exchange(request)
            # Freeze all processes while the trusted judge evaluates the returned value.
            self._pause()
            return response
        except BaseException:
            self.close()
            raise

    def _exchange(self, request):
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
        if type(response) is not dict or response.get("protocol") != 3:
            raise CandidateError("Invalid candidate value envelope")
        if type(response.get("sequence")) is not int or response["sequence"] != self.sequence:
            raise CandidateError("Unmatched candidate response")
        if set(response) == {"protocol", "sequence", "error", "detail", "phase"}:
            # A spoofed diagnostic can block completeness, but cannot earn correctness.
            # Codec failures require adjudication rather than penalizing a valid representation.
            if response["phase"] in ("decoding", "encoding"):
                raise CandidateInterfaceError(
                    str(response["error"]) + ": " + str(response["detail"])
                )
            if response["phase"] != "execution":
                raise CandidateError("Invalid candidate error phase")
            raise CandidateError(str(response["error"]) + ": " + str(response["detail"]))
        if set(response) != {"protocol", "sequence", "value", "args_after", "kwargs_after"}:
            raise CandidateError("Unexpected candidate envelope fields")
        return response

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
            if self.active_started is not None:
                self.active_seconds += time.monotonic() - self.active_started
                self.active_started = None
            for reader in self.readers:
                reader.join(timeout=2)
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                stream.close()
        self.directory.cleanup()
        if self.control is not None:
            self.control.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

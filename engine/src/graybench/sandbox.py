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

from graybench.artifacts import MAX_ARTIFACT_BYTES
from graybench.circuit_wire import WireLimitError
from graybench.container_control import ContainerControl
from graybench.value_wire import encode


class CandidateError(RuntimeError):
    pass


class SandboxInfrastructureError(RuntimeError):
    """Runtime bootstrap failed before candidate execution was authorized."""

    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


class CandidateInterfaceError(CandidateError):
    """Untrusted codec diagnostic requiring adjudication, never a scored verdict."""


class UnsupportedInterface(RuntimeError):
    pass


def decode(value, depth=0, budget=None):
    from graybench.value_wire import decode as decode_value

    try:
        return decode_value(value, depth, budget)
    except WireLimitError as exc:
        raise UnsupportedInterface(str(exc)) from exc
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
        opaque_input: bytes | None = None,
        protocol: int = 3,
        graph_session: str | None = None,
        graph_manifest: dict | None = None,
    ):
        if type(protocol) is not int or protocol not in (3, 4):
            raise ValueError("Unknown candidate protocol")
        if protocol == 4 and (
            type(graph_session) is not str
            or not 1 <= len(graph_session) <= 128
            or type(graph_manifest) is not dict
        ):
            raise ValueError("Graph protocol requires session and bootstrap manifest")
        self.protocol, self.graph_session = protocol, graph_session
        if opaque_input is not None and (
            type(opaque_input) is not bytes or len(opaque_input) > MAX_ARTIFACT_BYTES
        ):
            raise ValueError("Opaque input exceeds artifact byte limit")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("Candidate runtime must use an immutable local image digest")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Candidate timeout must be finite and positive")
        self.name = f"graybench-v{protocol}-" + uuid.uuid4().hex
        self.docker = docker
        self.timeout = timeout
        self.limit = output_limit
        self.sequence = 0
        self.directory = tempfile.TemporaryDirectory(prefix=f"graybench-v{protocol}-")
        self.process = None
        self.closed = False
        self.readers = []
        self.stderr = bytearray()
        self.messages = queue.Queue(maxsize=2)
        self.stopping = threading.Event()
        self.exceeded = threading.Event()
        self.wire_exceeded = threading.Event()
        self.active_seconds = 0.0
        self.bootstrap_seconds = None
        self.active_started = None
        self.paused = False
        self.control = None
        self.workspace = self.name + "-workspace"
        self.workspace_created = False
        directory = Path(self.directory.name)
        if opaque_input is not None:
            (directory / "artifact.bin").write_bytes(opaque_input)
        (directory / "candidate.py").write_text(code, encoding="utf-8")
        if public_prefix:
            (directory / "public_prefix.py").write_text(public_prefix, encoding="utf-8")
        worker = "graph_worker.py" if protocol == 4 else "worker.py"
        shutil.copyfile(Path(__file__).with_name(worker), directory / "worker.py")
        if protocol == 4:
            from graybench.graph_limits import GraphLimits
            from graybench.graph_runtime import stage_graph

            stage_graph(directory)
            (directory / "graph_config.json").write_text(
                json.dumps(
                    {
                        "session": graph_session,
                        "anchors": graph_manifest,
                        "limits": GraphLimits(message_bytes=output_limit).record(),
                    }
                ),
                encoding="utf-8",
            )
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
        shutil.copyfile(
            Path(__file__).with_name("instruction_wire.py"), directory / "instruction_wire.py"
        )
        shutil.copyfile(
            Path(__file__).with_name("operator_wire.py"), directory / "operator_wire.py"
        )
        shutil.copyfile(
            Path(__file__).with_name("primitive_wire.py"), directory / "primitive_wire.py"
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
            "--mount",
            f"type=volume,source={self.workspace},target=/tmp,volume-nocopy",
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
            self.control.create_workspace(self.workspace)
            self.workspace_created = True
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
            try:
                expected = {"protocol": protocol, "runtime_ready": True}
                if protocol == 4:
                    expected["anchors"] = graph_manifest
                if self._receive() != expected:
                    raise CandidateError("Runtime did not initialize the startup protocol")
            except (CandidateError, TimeoutError) as exc:
                raise SandboxInfrastructureError(
                    "Candidate runtime bootstrap failed",
                    {
                        "phase": "bootstrap",
                        "candidate_authorized": False,
                        "error_type": type(exc).__name__,
                        "elapsed_seconds": time.monotonic() - self.active_started,
                        "observed_stderr": self.stderr.decode(errors="replace"),
                    },
                ) from exc
            now = time.monotonic()
            self.bootstrap_seconds = now - self.active_started
            self.active_started = now
            self.deadline = now + timeout
            try:
                self.process.stdin.write(
                    json.dumps({"protocol": protocol, "start": True}).encode() + b"\n"
                )
                self.process.stdin.flush()
            except OSError as exc:
                raise SandboxInfrastructureError(
                    "Candidate start channel failed",
                    {
                        "phase": "start_channel",
                        "candidate_authorized": None,
                        "error_type": type(exc).__name__,
                        "bootstrap_seconds": self.bootstrap_seconds,
                        "observed_stderr": self.stderr.decode(errors="replace"),
                    },
                ) from exc
            if self._receive() != {"protocol": protocol, "ready": True}:
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
        while True:
            line = self.process.stdout.readline(self.limit + 1)
            if not line:
                self._queue(CandidateError("Candidate exited before returning a value"))
                return
            if self.stopping.is_set() or self.wire_exceeded.is_set():
                continue  # Drain without retention so Docker can close the attached process.
            total += len(line)
            if total > self.limit:
                self.wire_exceeded.set()
                self._queue(
                    CandidateInterfaceError("Candidate wire output exceeds transport limit")
                )
                continue
            self._queue(line)

    def _read_stderr(self):
        while True:
            chunk = self.process.stderr.read(8192)
            if not chunk:
                return
            if self.stopping.is_set() or self.exceeded.is_set():
                continue
            remaining = self.limit - len(self.stderr)
            self.stderr.extend(chunk[:remaining])
            if len(chunk) > remaining:
                self.exceeded.set()
                self._queue(CandidateError("Candidate diagnostic output limit exceeded"))

    def _receive(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Candidate sample time limit exceeded")
        try:
            message = self.messages.get(timeout=remaining)
        except queue.Empty as exc:
            raise TimeoutError("Candidate sample time limit exceeded") from exc
        if self.wire_exceeded.is_set():
            raise CandidateInterfaceError("Candidate wire output exceeds transport limit")
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

    def capture_artifact(self, name: str, *, limit=MAX_ARTIFACT_BYTES):
        """Capture actual file bytes while every candidate process remains frozen."""
        if self.closed or not self.paused or self.control is None:
            raise RuntimeError("Artifact capture requires a live paused candidate")
        return self.control.capture_artifact(self.name, name, limit=limit)

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

    def call_encoded(self, entry_point: str, args_wire, kwargs_wire, *, discard_result=False):
        """Forward a trusted judge's typed inputs without host object reconstruction."""
        if self.protocol != 3:
            raise CandidateError("Value calls are not valid in a graph session")
        self.sequence += 1
        request = (
            json.dumps(
                {
                    "entry_point": entry_point,
                    "args": args_wire,
                    "kwargs": kwargs_wire,
                    "sequence": self.sequence,
                    "discard_result": discard_result,
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

    def call_graph(self, entry_point, graph, *, discard_result=False):
        """Relay a graph envelope without constructing any candidate object on the host."""
        if self.protocol != 4:
            raise CandidateError("Graph calls require protocol4")
        self.sequence += 1
        request = (
            json.dumps(
                {
                    "protocol": 4,
                    "session": self.graph_session,
                    "sequence": self.sequence,
                    "entry_point": entry_point,
                    "graph": graph,
                    "discard_result": discard_result,
                },
                allow_nan=False,
            ).encode()
            + b"\n"
        )
        if len(request) > self.limit:
            raise CandidateInterfaceError("Graph call input exceeds transport limit")
        try:
            self._resume()
            response = self._exchange(request)
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
        if (
            type(response) is not dict
            or type(response.get("protocol")) is not int
            or response["protocol"] != self.protocol
        ):
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
        expected = (
            {"protocol", "sequence", "graph", "exception"}
            if self.protocol == 4
            else {"protocol", "sequence", "value", "args_after", "kwargs_after"}
        )
        if set(response) != expected:
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
            try:
                if self.workspace_created:
                    self.control.remove_workspace(self.workspace)
            finally:
                self.control.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

"""Bidirectional isolated upstream-test bridge, with explicit unsupported interface outcomes."""

import ast
import hashlib
import json
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from graybench.contracts import ExtractionPolicy
from graybench.datasets import JudgeTask
from graybench.extraction import EXTRACTION_POLICIES, extract
from graybench.identity import canonical, identity
from graybench.judge import Judgment, ProtectedJudge
from graybench.sandbox import (
    Candidate,
    CandidateError,
    CandidateInterfaceError,
    SandboxInfrastructureError,
)
from graybench.upstream_evidence import CAPTURE, capture_judgment

FILES = (
    "upstream_process.py",
    "value_wire.py",
    "circuit_wire.py",
    "scientific_wire.py",
    "symbolic_wire.py",
    "preparation_wire.py",
    "instruction_wire.py",
    "operator_wire.py",
    "primitive_wire.py",
)


class UpstreamJudge:
    def __init__(
        self,
        *,
        image: str,
        docker="docker",
        timeout=120,
        candidate_timeout=120,
        output_limit=1024 * 1024,
        protocol=3,
        graph_transport="snapshot-v1",
        graph_state_limit=None,
        graph_batch="none",
        extraction: ExtractionPolicy = "raw_or_single_python_fence_v1",
    ):
        if type(protocol) is not int or protocol not in (3, 4):
            raise ValueError("Unknown upstream bridge protocol")
        if extraction not in EXTRACTION_POLICIES:
            raise ValueError("Unknown extraction policy")
        self.extraction = extraction
        self.protocol = protocol
        from graybench.graph_limits import transport_record

        if graph_batch not in ("none", "positional-batch-v1"):
            raise ValueError("Unknown graph batch mode")
        if protocol != 4 and (
            graph_transport != "snapshot-v1"
            or graph_state_limit is not None
            or graph_batch != "none"
        ):
            raise ValueError("Graph transport settings require protocol4")
        self.graph_batch = graph_batch
        self.graph_transport = (
            transport_record(graph_transport, output_limit, graph_state_limit)
            if protocol == 4
            else None
        )
        # Use the same immutable-image/resource validation as the fixed-oracle judge.
        ProtectedJudge(image=image, docker=docker, timeout=timeout, output_limit=output_limit)
        self.image, self.docker, self.timeout = image, docker, float(timeout)
        self.candidate_timeout, self.limit = float(candidate_timeout), output_limit

    def configuration(self, task: JudgeTask) -> tuple[dict, dict]:
        """Describe exact private judge input and runtime without executing a candidate."""
        prefix = ""
        if task.public.suite == "normal":
            tree = ast.parse(task.public.prompt)
            definition = next(
                n
                for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == task.public.entry_point
            )
            prefix = "".join(task.public.prompt.splitlines(keepends=True)[: definition.lineno - 1])
        # Canonical solutions never enter either mount through this task payload.
        payload = {
            "test": task.upstream_test,
            "prefix": prefix,
            "entry_point": task.public.entry_point,
        }
        if self.protocol == 4:
            from graybench.graph_limits import GraphLimits

            payload["graph_limits"] = GraphLimits(
                message_bytes=self.graph_transport["state_bytes"]
            ).record()
            payload["graph_transport"] = dict(self.graph_transport)
            if self.graph_batch != "none":
                payload["graph_batch"] = self.graph_batch
        source = Path(__file__).parent
        files = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in FILES}
        for name in (
            "upstream.py",
            "sandbox.py",
            "worker.py",
            "extraction.py",
            "container_control.py",
            "artifacts.py",
            "upstream_evidence.py",
        ):
            files[name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if self.protocol == 4:
            from graybench.graph_runtime import GRAPH_FILES

            for name in (
                *GRAPH_FILES,
                "graph_runtime.py",
                "graph_worker.py",
                "upstream_graph_process.py",
            ):
                files[name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
        manifest = {
            "files": files,
            "image": self.image,
            "task_payload": identity(payload),
            "judge_timeout": self.timeout,
            "candidate_timeout": self.candidate_timeout,
            "candidate_timing": "active-wall-v3-after-runtime-bootstrap",
            "candidate_startup": "runtime-ready-host-start-candidate-ready-v1",
            "candidate_workspace": "isolated-local-tmpfs-volume-v1-256MiB",
            "output_limit": self.limit,
            "extraction_policy": self.extraction,
            "trusted_judgment_capture": CAPTURE,
            "protocol": "upstream-graph-v4" if self.protocol == 4 else "upstream-proxy-v1",
            **(
                {
                    "graph_roots": "args-kwargs-result-exception_args-v1",
                    "graph_bootstrap": "qiskit-public-anchors-before-user-code-v1",
                    "graph_session_policy": "random-per-attempt-v1",
                    "graph_exceptions": "basic-builtin-type-and-args-v1",
                    "graph_limits": payload["graph_limits"],
                    "graph_transport": payload["graph_transport"],
                    "wire_output_accounting": "cumulative-per-process-including-bootstrap-v1",
                    **(
                        {"graph_batch": self.graph_batch, "batch_case_limit": 1024}
                        if self.graph_batch != "none"
                        else {}
                    ),
                }
                if self.protocol == 4
                else {}
            ),
        }
        return payload, manifest

    def evaluate(self, task: JudgeTask, completion: str) -> Judgment:
        extracted = extract(completion, task.public, self.extraction)
        payload, manifest = self.configuration(task)
        source = Path(__file__).parent
        digest = identity(manifest)
        if extracted.error:
            return Judgment(
                "candidate_error",
                digest,
                {
                    "detail": extracted.error,
                    "extraction_method": extracted.method,
                    "manifest": manifest,
                    "termination_source": "host_error",
                    "completion_sha256": hashlib.sha256(completion.encode()).hexdigest(),
                    "public_task_digest": task.public.digest,
                },
            )
        graph_session = uuid.uuid4().hex if self.protocol == 4 else None
        runtime_payload = (
            {**payload, "graph_session": graph_session} if self.protocol == 4 else payload
        )
        name = "graybench-upstream-" + uuid.uuid4().hex
        messages = queue.Queue(maxsize=2)
        stopping, exceeded = threading.Event(), threading.Event()
        stderr = bytearray()
        process, candidate = None, None
        readers = []
        transcript = []
        start = time.monotonic()
        judge_wait = 0.0

        def put(item):
            while not stopping.is_set():
                try:
                    messages.put(item, timeout=0.1)
                    return
                except queue.Full:
                    pass

        def read_stdout():
            count = 0
            while not stopping.is_set():
                line = process.stdout.readline(self.limit + 1)
                count += len(line)
                if count > self.limit:
                    exceeded.set()
                    put(None)
                    return
                if not line:
                    put(None)
                    return
                put(line)

        def read_stderr():
            while not stopping.is_set():
                chunk = process.stderr.read(8192)
                if not chunk:
                    return
                remaining = max(0, self.limit - len(stderr))
                stderr.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    exceeded.set()
                    put(None)
                    return

        def finish(outcome, evidence, *, terminal=None):
            return Judgment(
                outcome,
                digest,
                {
                    **evidence,
                    "manifest": manifest,
                    "termination_source": "trusted_judgment"
                    if terminal is not None
                    else "host_error",
                    **(
                        {
                            "graph_session": graph_session,
                            "runtime_task_payload_digest": identity(runtime_payload),
                        }
                        if self.protocol == 4
                        else {}
                    ),
                    "transcript": transcript,
                    "judge_wait_seconds": judge_wait,
                    "candidate_active_seconds": candidate.active_seconds if candidate else None,
                    "candidate_bootstrap_seconds": candidate.bootstrap_seconds
                    if candidate
                    else None,
                    "wall_seconds": time.monotonic() - start,
                    "completion_sha256": hashlib.sha256(completion.encode()).hexdigest(),
                    "extracted_code_sha256": hashlib.sha256(extracted.code.encode()).hexdigest(),
                    "extraction_method": extracted.method,
                    "public_task_digest": task.public.digest,
                    **(
                        {
                            "trusted_judgment": terminal[0],
                            "trusted_judgment_artifact": terminal[1],
                        }
                        if terminal is not None
                        else {}
                    ),
                },
            )

        with tempfile.TemporaryDirectory(prefix="graybench-upstream-") as directory:
            root = Path(directory)
            (root / "task.json").write_bytes(canonical(runtime_payload))
            for filename in FILES:
                shutil.copyfile(source / filename, root / filename)
            if self.protocol == 4:
                from graybench.graph_runtime import stage_graph

                stage_graph(root)
                shutil.copyfile(source / "upstream_graph_process.py", root / "upstream_process.py")
            args = [
                self.docker,
                "run",
                "--rm",
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
                "MPLCONFIGDIR=/tmp/matplotlib",
                "--env",
                "MPLBACKEND=Agg",
                "--env",
                "OMP_NUM_THREADS=1",
                self.image,
                "python",
                "-u",
                "/judge/upstream_process.py",
            ]
            try:
                process = subprocess.Popen(
                    args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
                readers = [
                    threading.Thread(target=read_stdout, daemon=True),
                    threading.Thread(target=read_stderr, daemon=True),
                ]
                for reader in readers:
                    reader.start()
                sequence = 0
                while True:
                    waiting = time.monotonic()
                    try:
                        raw = messages.get(timeout=max(0.001, self.timeout - judge_wait))
                    except queue.Empty:
                        return finish("infrastructure_error", {"detail": "trusted judge timed out"})
                    judge_wait += time.monotonic() - waiting
                    if raw is None or exceeded.is_set():
                        return finish(
                            "infrastructure_error",
                            {
                                "detail": "judge exited or exceeded output",
                                "stderr": stderr.decode(errors="replace"),
                            },
                        )
                    message = json.loads(raw)
                    if type(message) is not dict:
                        raise ValueError("Invalid trusted message envelope")
                    if message.get("kind") == "judgment":
                        terminal = capture_judgment(raw, limit=self.limit)
                        return finish(
                            terminal[0]["outcome"], terminal[0]["evidence"], terminal=terminal
                        )
                    sequence += 1
                    if message.get("kind") != "call" or message.get("sequence") != sequence:
                        raise ValueError("Invalid trusted call")
                    batch = message.get("batch", False)
                    if type(batch) is not bool or (
                        batch and self.graph_batch != "positional-batch-v1"
                    ):
                        raise ValueError("Undeclared graph batch call")
                    if sequence > 1000:
                        return finish("unsupported", {"detail": "call count exceeds bridge limit"})
                    try:
                        if candidate is None:
                            candidate = Candidate(
                                extracted.code,
                                public_prefix=extracted.public_prefix,
                                image=self.image,
                                docker=self.docker,
                                timeout=self.candidate_timeout,
                                output_limit=self.limit,
                                **(
                                    {
                                        "protocol": 4,
                                        "graph_session": graph_session,
                                        "graph_manifest": message["graph"]["anchors"],
                                        "graph_transport": self.graph_transport["mode"],
                                        "graph_state_limit": self.graph_transport["state_bytes"],
                                        "graph_batch": self.graph_batch,
                                    }
                                    if self.protocol == 4
                                    else {}
                                ),
                            )
                        if self.protocol == 4:
                            returned = candidate.call_graph(
                                task.public.entry_point, message["graph"], batch=batch
                            )
                        else:
                            returned = candidate.call_encoded(
                                task.public.entry_point, message["args"], message["kwargs"]
                            )
                        response = {
                            "sequence": sequence,
                            "outcome": "returned",
                            "response": returned,
                        }
                    except CandidateInterfaceError as exc:
                        response = {
                            "sequence": sequence,
                            "outcome": "unsupported",
                            "detail": str(exc),
                        }
                    except CandidateError as exc:
                        response = {
                            "sequence": sequence,
                            "outcome": "candidate_error",
                            "detail": str(exc),
                        }
                    except TimeoutError as exc:
                        response = {"sequence": sequence, "outcome": "timeout", "detail": str(exc)}
                    transcript.append(
                        {
                            "call": identity(message),
                            "response": identity(response),
                            "call_data": message,
                            "response_data": response,
                        }
                    )
                    data = canonical(response) + b"\n"
                    # A correct trusted proxy is already waiting for this response. A writer
                    # thread still bounds failure if the judge crashes before consuming it.
                    errors = []

                    def send(data=data, errors=errors):
                        try:
                            process.stdin.write(data)
                            process.stdin.flush()
                        except OSError as exc:
                            errors.append(exc)

                    sender = threading.Thread(target=send, daemon=True)
                    readers.append(sender)
                    sender.start()
                    sender.join(timeout=max(0.001, self.timeout - judge_wait))
                    if sender.is_alive() or errors:
                        return finish(
                            "infrastructure_error", {"detail": "judge response pipe failed"}
                        )
            except SandboxInfrastructureError as exc:
                return finish("infrastructure_error", {"runtime_failure": exc.evidence})
            except (OSError, ValueError, TypeError) as exc:
                return finish(
                    "infrastructure_error", {"exception": type(exc).__name__, "detail": str(exc)}
                )
            finally:
                stopping.set()
                if candidate is not None:
                    candidate.close()
                try:
                    subprocess.run(
                        [self.docker, "rm", "--force", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    pass
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=10)
                    for reader in readers:
                        reader.join(timeout=2)
                    for stream in (process.stdin, process.stdout, process.stderr):
                        stream.close()

"""Development task-82 semantic track with separate candidate, parser and oracle containers."""

import base64
import hashlib

from graybench.artifacts import ArtifactUnsupported
from graybench.extraction import extract
from graybench.identity import identity
from graybench.judge import Judgment, ProtectedJudge
from graybench.provenance import source_manifest
from graybench.qpy_decoder import decode_qpy
from graybench.sandbox import Candidate, CandidateError, CandidateInterfaceError
from graybench.value_wire import encode


class QpyFileJudge:
    def __init__(
        self, *, image, docker="docker", candidate_timeout=120, parser_timeout=30, timeout=30
    ):
        self.image, self.docker = image, docker
        self.candidate_timeout, self.parser_timeout = candidate_timeout, parser_timeout
        self.oracle = ProtectedJudge(image=image, docker=docker, timeout=timeout)

    def configuration(self, task):
        if (
            task.public.family_id != "qhe/82"
            or task.public.entry_point != "create_binary_serialization"
        ):
            raise ValueError("This explicit semantic track requires task 82")
        manifest = {
            "track": "task82-file-semantic-v1",
            "source": source_manifest(),
            "task_digest": task.digest,
            "image": self.image,
            "candidate_timeout": self.candidate_timeout,
            "parser_timeout": self.parser_timeout,
            "oracle": self.oracle.manifest("task82-bell-file-state-v1"),
            "artifact": {"name": "bell.qpy", "max_bytes": 4 * 1024 * 1024},
            "return_value": "ignored as in upstream check",
            "release_eligible": False,
        }
        return {}, manifest

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        digest = identity(manifest)
        evidence = {
            "manifest": manifest,
            "completion_sha256": hashlib.sha256(completion.encode()).hexdigest(),
        }

        def finish(outcome, **extra):
            return Judgment(outcome, digest, {**evidence, **extra})

        extracted = extract(completion, task.public)
        if extracted.error:
            return finish("candidate_error", detail=extracted.error)
        phase = "candidate"
        try:
            with Candidate(
                extracted.code,
                public_prefix=extracted.public_prefix,
                image=self.image,
                docker=self.docker,
                timeout=self.candidate_timeout,
            ) as candidate:
                candidate.call_encoded(
                    task.public.entry_point, encode(()), encode({}), discard_result=True
                )
                phase = "capture"
                artifact = candidate.capture_artifact("bell.qpy")
                evidence["candidate_active_seconds"] = candidate.active_seconds
                evidence["artifact"] = artifact.manifest
                evidence["artifact_bytes_base64"] = base64.b64encode(artifact.data).decode()
            phase = "parser"
            wire, parser_evidence = decode_qpy(
                artifact.data,
                image=self.image,
                docker=self.docker,
                timeout=self.parser_timeout,
            )
            evidence["parser"] = parser_evidence
            phase = "oracle"
            judgment = self.oracle.evaluate(wire, oracle="task82-bell-file-state-v1")
            return finish(judgment.outcome, oracle_evidence=judgment.evidence)
        except FileNotFoundError as exc:
            # Missing required output is a scored failure only during artifact capture.
            return finish("fail" if phase == "capture" else "infrastructure_error", detail=str(exc))
        except (CandidateInterfaceError, ArtifactUnsupported) as exc:
            return finish("unsupported", phase=phase, detail=str(exc))
        except CandidateError as exc:
            # Parser rejection/crash is unresolved until malformed files can be distinguished
            # from parser/interface limitations. It never becomes an automatic wrong answer.
            return finish(
                "candidate_error" if phase == "candidate" else "unsupported",
                phase=phase,
                detail=str(exc),
            )
        except TimeoutError as exc:
            return finish(
                "timeout" if phase == "candidate" else "unsupported", phase=phase, detail=str(exc)
            )
        except Exception as exc:
            return finish(
                "infrastructure_error", phase=phase, exception=type(exc).__name__, detail=str(exc)
            )

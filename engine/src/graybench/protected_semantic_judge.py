"""Trusted, host-side semantic checks for explicitly revised value tasks.

Candidate output is a declared JSON answer. It cannot attest Qiskit object
identity, algorithm use, or any side effect inside the candidate process.
"""

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from graybench.contracts import Contract
from graybench.datasets import JudgeTask
from graybench.identity import identity
from graybench.protected_value_contract import ProtectedValueContract, ValueCall
from graybench.protected_value_runner import ValueRunner

TASK20_ORACLE = "task20-seven-qubit-ghz-amplitudes-v1"


class SemanticCase(Contract):
    case_id: str = Field(min_length=1)
    call: ValueCall


class ProtectedSemanticTask(Contract):
    schema_version: Literal["1"] = "1"
    contract: ProtectedValueContract
    oracle: Literal["task20-seven-qubit-ghz-amplitudes-v1"] = TASK20_ORACLE
    cases: tuple[SemanticCase, ...] = Field(min_length=1, max_length=64)
    release_eligible: Literal[False] = False

    @model_validator(mode="after")
    def valid_cases(self) -> "ProtectedSemanticTask":
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Semantic case identities must be unique")
        if len({case.call.digest for case in self.cases}) != len(self.cases):
            raise ValueError("Semantic cases must exercise distinct call inputs")
        return self


@dataclass(frozen=True)
class SemanticJudgment:
    outcome: str
    judge_digest: str
    evidence: dict


def _task20_ghz_value(layout: object, value: object) -> dict:
    """Check a normalized GHZ+ amplitude vector on selected physical wires."""
    if (
        type(layout) is not list
        or len(layout) != 3
        or any(type(wire) is not int or not 0 <= wire < 7 for wire in layout)
        or len(set(layout)) != 3
        or type(value) is not list
        or len(value) != 128
    ):
        return {"passed": False, "reason": "invalid_case_or_value"}
    try:
        amplitudes = [complex(real, imaginary) for real, imaginary in value]
    except (TypeError, ValueError, OverflowError):
        return {"passed": False, "reason": "invalid_amplitude"}
    norm = sum(abs(amplitude) ** 2 for amplitude in amplitudes)
    target = (amplitudes[0] + amplitudes[sum(1 << wire for wire in layout)]) / math.sqrt(2)
    fidelity = abs(target) ** 2
    passed = math.isclose(norm, 1.0, abs_tol=1e-8, rel_tol=0) and math.isclose(
        fidelity, 1.0, abs_tol=1e-8, rel_tol=0
    )
    return {"passed": passed, "norm": norm, "fidelity": fidelity}


class ProtectedSemanticJudge:
    def __init__(self, runner: ValueRunner):
        self.runner = runner

    def manifest(self, task: ProtectedSemanticTask) -> dict:
        return {
            "track": task.contract.track,
            "source_task_digest": task.contract.source_task_digest,
            "public_contract_digest": task.contract.digest,
            "private_case_digest": identity([case.model_dump(mode="json") for case in task.cases]),
            "oracle": task.oracle,
            "oracle_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "task20_contract_code_sha256": hashlib.sha256(
                Path(__file__).with_name("protected_task20.py").read_bytes()
            ).hexdigest(),
            "runner": self.runner.manifest(task.contract),
            "release_eligible": False,
        }

    def evaluate(
        self, task: ProtectedSemanticTask, source: JudgeTask, completion: str
    ) -> SemanticJudgment:
        manifest = self.manifest(task)
        digest = identity(manifest)
        evidence = {
            "manifest": manifest,
            "origin_claim": "candidate_submitted_value_only",
            "native_object_attested": False,
            "pass_manager_use_attested": False,
            "release_eligible": False,
        }
        if (
            source.digest != task.contract.source_task_digest
            or source.public.suite != task.contract.public.suite
            or source.public.task_id != task.contract.public.task_id
        ):
            return SemanticJudgment(
                "infrastructure_error", digest, {**evidence, "reason": "source_digest_mismatch"}
            )
        execution = self.runner.execute(
            task.contract, completion, tuple(case.call for case in task.cases)
        )
        evidence["candidate_execution"] = execution.evidence
        if execution.outcome != "returned":
            return SemanticJudgment(execution.outcome, digest, evidence)
        if len(execution.values) != len(task.cases):
            return SemanticJudgment(
                "infrastructure_error", digest, {**evidence, "reason": "case_count_mismatch"}
            )
        case_results = []
        for case, value in zip(task.cases, execution.values, strict=True):
            result = _task20_ghz_value(case.call.args[0], value)
            case_results.append({"case_id": case.case_id, **result})
        evidence["case_results"] = case_results
        return SemanticJudgment(
            "pass" if all(result["passed"] for result in case_results) else "fail",
            digest,
            evidence,
        )

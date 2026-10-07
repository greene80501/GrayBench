"""Bind campaign verdicts to frozen tasks, judges and returned generation records.

These are local consistency checks. An unsigned ledger does not authenticate
its author, prove which code actually ran, or qualify an oracle for publication.
"""

import hashlib
import json
import re

from graybench.identity import identity
from graybench.upstream_evidence import OUTCOMES, verify_review_judgment

POLICY = "cohort-bound-v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _digest(value):
    return type(value) is str and HEX.fullmatch(value) is not None


def completion_binding(completion):
    try:
        raw = completion.encode("utf-8")
        encoding = None
    except UnicodeEncodeError:
        raw = completion.encode("utf-8", "surrogatepass")
        encoding = "utf-8-surrogatepass"
    return {
        "completion_sha256": hashlib.sha256(raw).hexdigest(),
        **({"completion_digest_encoding": encoding} if encoding else {}),
    }


def _completion_matches(evidence, completion, *, depth=0):
    if depth > 16 or type(evidence) is not dict:
        raise ValueError("Invalid nested completion evidence")
    found = 0
    if "completion_sha256" in evidence:
        expected = completion_binding(completion)
        if any(
            evidence.get(field) != expected.get(field)
            for field in ("completion_sha256", "completion_digest_encoding")
        ):
            raise ValueError("Judged completion differs from returned generation text")
        found = 1
    for field in ("inner", "candidate_execution"):
        if field in evidence:
            found += _completion_matches(evidence[field], completion, depth=depth + 1)
    return found


def validate_judgment_result(
    outcome, evidence, task_judge_digest, *, completion=None, require_completion=False
):
    if (
        type(outcome) is not str
        or outcome not in OUTCOMES
        or type(evidence) is not dict
        or type(evidence.get("manifest")) is not dict
        or identity(evidence["manifest"]) != task_judge_digest
    ):
        raise ValueError("Campaign judgment manifest differs from frozen task judge")
    verify_review_judgment(outcome, evidence)
    if completion is not None:
        found = _completion_matches(evidence, completion)
        if require_completion and outcome in {"pass", "fail"} and not found:
            raise ValueError("Scored judgment lacks its judged completion binding")
    elif require_completion:
        raise ValueError("Missing returned completion text")
    # Native results are parsed observations, not trusted-process attestations.
    if (
        evidence["manifest"].get("track") == "qhe-pinned-native-v1"
        and outcome in {"pass", "fail"}
        and "worker_result" not in evidence
    ):
        raise ValueError("Scored native verdict lacks its captured native worker result")
    if "worker_result" in evidence:
        result = evidence["worker_result"]
        if (
            type(result) is not dict
            or result.get("completed") is not True
            or result.get("status") != outcome
            or outcome not in {"pass", "fail", "candidate_error", "infrastructure_error"}
            or type(result.get("phase")) is not str
            or set(result) - {"completed", "status", "phase", "exception_type", "detail"}
        ):
            raise ValueError("Campaign outcome differs from captured native worker result")
        # The pinned worker writes this exact JSON encoding. This is consistency
        # with a parsed same-process result, not protection against its author.
        raw = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        artifact = evidence.get("result_artifact")
        expected = {
            "name": "result.json",
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "capture": "isolated-ephemeral-host-bind-v1",
        }
        if artifact != expected:
            raise ValueError("Captured native result artifact differs from worker result")
    if evidence["manifest"].get("track") == "graybench-protected-semantic-v1" and outcome in {
        "pass",
        "fail",
    }:
        cases = evidence.get("case_results")
        if (
            type(cases) is not list
            or not cases
            or any(
                type(case) is not dict
                or type(case.get("case_id")) is not str
                or not case["case_id"]
                or type(case.get("passed")) is not bool
                for case in cases
            )
        ):
            raise ValueError("Missing or invalid protected case results")
        ids = [case["case_id"] for case in cases]
        declared = evidence["manifest"].get("case_ids")
        if (
            len(set(ids)) != len(ids)
            or (declared is not None and ids != declared)
            or (require_completion and declared is None)
            or ((outcome == "pass") != all(case["passed"] for case in cases))
        ):
            raise ValueError("Protected outcome or case roster differs from declared case results")


def campaign_judgment_binding(
    protocol, task_key, generation_digest, outcome, evidence, *, completion=None
):
    """Validate a claimed binding; old undeclared bare evidence stays visibly unbound."""
    if type(evidence) is not dict or type(outcome) is not str or outcome not in OUTCOMES:
        raise ValueError("Invalid campaign judgment evidence or outcome")
    claimed = any(
        key in evidence for key in ("cohort", "generation_digest", "task_judge_digest", "judgment")
    )
    if not claimed and protocol.judgment_evidence_policy is None:
        verify_review_judgment(outcome, evidence)
        return "legacy_unbound"
    cohort = evidence.get("cohort")
    if (
        type(cohort) is not dict
        or set(cohort) != {"dataset_digest", "judge_digest", "runtime_digest", "tasks", "judges"}
        or evidence.get("generation_digest") != generation_digest
        or not _digest(generation_digest)
        or task_key not in protocol.task_keys
    ):
        raise ValueError("Campaign judgment lacks its exact generation/cohort binding")
    tasks, judges = cohort["tasks"], cohort["judges"]
    if (
        type(tasks) is not dict
        or type(judges) is not dict
        or set(tasks) != set(protocol.task_keys)
        or set(judges) != set(protocol.task_keys)
        or any(not _digest(value) for value in judges.values())
        or identity(tasks) != protocol.dataset_digest
        or identity(judges) != protocol.judge_digest
        or any(
            cohort[field] != getattr(protocol, field)
            for field in ("dataset_digest", "judge_digest", "runtime_digest")
        )
    ):
        raise ValueError("Campaign judgment cohort differs from frozen protocol")
    for record in tasks.values():
        valid = (
            type(record) is dict
            and set(record) == {"source", "revised_task"}
            and all(_digest(value) for value in record.values())
            if protocol.track == "graybench-protected-semantic-v1"
            else _digest(record)
        )
        if not valid:
            raise ValueError("Invalid campaign task identity")
    base = {"cohort", "generation_digest"}
    if set(evidence) in (base | {"error_type"}, base | {"error_type", "rejected_judgment"}):
        if (
            outcome != "infrastructure_error"
            or type(evidence["error_type"]) is not str
            or not evidence["error_type"].strip()
        ):
            raise ValueError("A host judgment exception cannot claim a candidate verdict")
        if "rejected_judgment" in evidence:
            rejected = evidence["rejected_judgment"]
            if type(rejected) is not dict or set(rejected) != {
                "outcome",
                "judge_digest",
                "evidence",
            }:
                raise ValueError("Invalid rejected-judgment diagnostic")
        return "bound"
    if (
        set(evidence) != base | {"task_judge_digest", "judgment"}
        or evidence["task_judge_digest"] != judges[task_key]
    ):
        raise ValueError("Campaign judgment differs from frozen task judge")
    validate_judgment_result(
        outcome,
        evidence["judgment"],
        judges[task_key],
        completion=completion,
        require_completion=protocol.judgment_evidence_policy is not None,
    )
    return "bound"

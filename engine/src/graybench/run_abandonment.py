"""Explicit terminal closure of an incomplete run; never recovery of a model score."""

from typing import Literal

from pydantic import Field, model_validator

from graybench.contracts import Contract, reject_model_credential
from graybench.identity import canonical
from graybench.ledger import StateError, now
from graybench.provenance import source_manifest


class AbandonmentPlan(Contract):
    method: Literal["abandon-incomplete-run-v1"] = "abandon-incomplete-run-v1"
    run_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    protocol_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    analysis_source: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=4096)
    workers_stopped: bool = Field(strict=True)
    snapshot: dict

    @model_validator(mode="after")
    def explicit_stop(self):
        if not self.reason.strip() or self.workers_stopped is not True:
            raise ValueError("A reason and explicit stopped-worker declaration are required")
        return self


class AbandonmentRecord(Contract):
    state: Literal["abandoned"] = "abandoned"
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan: AbandonmentPlan
    recorded_at: str
    publication_eligible: Literal[False] = False
    workers_stopped_status: Literal["operator_declared_not_externally_verified"] = (
        "operator_declared_not_externally_verified"
    )
    scope: Literal["terminal incomplete run; original evidence retained; no score repaired"] = (
        "terminal incomplete run; original evidence retained; no score repaired"
    )


def completed_cohort(snapshot):
    """Source drift alone must not make a finished archived score abandonable."""
    return snapshot["complete"] or (set(snapshot["score_blockers"]) == {"analysis_source_mismatch"})


def plan_abandonment(ledger, run_id, *, reason, workers_stopped):
    # Validate operator fields before reading or writing any ledger state.
    plan = AbandonmentPlan(
        run_id=run_id,
        protocol_digest="0" * 64,
        analysis_source=source_manifest()["digest"],
        reason=reason,
        workers_stopped=workers_stopped,
        snapshot={},
    )
    ledger.db.execute("BEGIN")
    try:
        ledger.require_run_open(run_id)
        protocol = ledger.protocol(run_id)
        snapshot = ledger._summary(run_id)
        if completed_cohort(snapshot):
            raise StateError("A complete run cannot be abandoned")
        reject_model_credential(protocol.model, reason, "abandonment reason")
        plan = plan.model_copy(
            update={
                "protocol_digest": ledger.protocol_manifest_digest(run_id),
                "snapshot": snapshot,
            }
        )
        ledger.db.execute("COMMIT")
    except BaseException:
        ledger.db.execute("ROLLBACK")
        raise
    return plan


def abandon_run(ledger, plan):
    plan = AbandonmentPlan.model_validate_json(canonical(plan.model_dump(mode="json")))
    if plan.analysis_source != source_manifest()["digest"]:
        raise StateError("Abandonment analysis source changed")
    with ledger.transaction():
        ledger.require_run_open(plan.run_id)
        protocol = ledger.protocol(plan.run_id)
        reject_model_credential(protocol.model, plan.model_dump(mode="json"), "abandonment plan")
        snapshot = ledger._summary(plan.run_id)
        if ledger.protocol_manifest_digest(plan.run_id) != plan.protocol_digest or canonical(
            snapshot
        ) != canonical(plan.snapshot):
            raise StateError("Abandonment plan differs from the exact current ledger snapshot")
        if completed_cohort(snapshot):
            raise StateError("A complete run cannot be abandoned")
        record = {
            "state": "abandoned",
            "plan_digest": plan.digest,
            "plan": plan.model_dump(mode="json"),
            "recorded_at": now(),
            "publication_eligible": False,
            "workers_stopped_status": "operator_declared_not_externally_verified",
            "scope": "terminal incomplete run; original evidence retained; no score repaired",
        }
        record = AbandonmentRecord.model_validate_json(canonical(record)).model_dump(mode="json")
        content = ledger._blob(record)
        ledger.db.execute(
            "INSERT INTO run_abandonments VALUES (?,?,?)",
            (plan.run_id, content, record["recorded_at"]),
        )
        ledger._event("run_abandoned", run_id=plan.run_id, content=content)
    return record

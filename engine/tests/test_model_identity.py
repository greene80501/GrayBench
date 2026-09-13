import pytest

from graybench.contracts import Generation, ModelSpec, Protocol
from graybench.ledger import StateError
from graybench.providers import Ollama


@pytest.mark.parametrize("returned_name", [None, "", "different-model"])
def test_missing_or_changed_model_is_retained_but_never_scored(
    ledger, protocol, task, returned_name
):
    protocol = protocol.model_copy(update={"repeats": 2})
    run = ledger.create_run(protocol)
    first, second = ledger.samples(run)
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(first["id"], request)
    ledger.finish_attempt(
        attempt,
        "returned",
        {},
        200,
        Generation(
            text="answer",
            returned_model=returned_name,
            response_id=None,
            finish_reason="stop",
            usage={},
        ),
    )
    ledger.judge(first["id"], protocol.judge_digest, "pass", {})
    assert ledger.summary(run)["returned_samples"] == 1
    assert ledger.summary(run)["model_identity"]["status"] == "unresolved"
    assert ledger.summary(run)["pass_at_1"] is None
    with pytest.raises(StateError, match="identity"):
        ledger.begin_attempt(second["id"], request)


def test_predeclared_snapshot_name_with_evidence_is_accepted(ledger, protocol, task):
    spec = ModelSpec.model_validate_json(
        protocol.model.model_copy(
            update={
                "accepted_returned_models": ("snapshot-2026-01",),
                "model_identity_evidence": "fixture documented mapping pinned before generation",
            }
        ).model_dump_json()
    )
    protocol = protocol.model_copy(update={"model": spec})
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(spec, task, None))
    ledger.finish_attempt(
        attempt,
        "returned",
        {},
        200,
        Generation(
            text="answer",
            returned_model="snapshot-2026-01",
            response_id=None,
            finish_reason="stop",
            usage={},
        ),
    )
    ledger.judge(sample, protocol.judge_digest, "pass", {})
    summary = ledger.summary(run)
    assert summary["pass_at_1"] == 1
    assert summary["model_identity"]["weights_identity"] == "not_verified"


def test_aliases_require_evidence(model):
    with pytest.raises(ValueError, match="evidence"):
        ModelSpec.model_validate_json(
            model.model_copy(update={"accepted_returned_models": ("snapshot",)}).model_dump_json()
        )


def test_old_protocol_is_not_silently_reinterpreted(protocol):
    with pytest.raises(ValueError):
        Protocol.model_validate_json(
            protocol.model_copy(update={"schema_version": "3.0"}).model_dump_json()
        )

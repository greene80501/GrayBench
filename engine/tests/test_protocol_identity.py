"""Archived protocol bytes remain the authority for run identity."""

import json
import sys
import uuid

import pytest

from graybench.cli import main
from graybench.identity import identity
from graybench.ledger import StateError, now
from graybench.providers import Ollama


def legacy_manifest(protocol):
    value = protocol.model_dump(mode="json")
    del value["model"]["discovery_policy"]
    del value["model"]["discovery_exception_reason"]
    return value


def archived_run(ledger, protocol):
    """Model the append-only records written before discovery defaults existed."""
    raw = legacy_manifest(protocol)
    run_id = uuid.uuid4().hex
    with ledger.transaction():
        manifest = ledger._blob(raw)
        ledger.db.execute("INSERT INTO runs VALUES (?,?,?)", (run_id, manifest, now()))
        for task in protocol.task_keys:
            for replicate in range(protocol.repeats):
                sample_id = identity([run_id, task, replicate])
                ledger.db.execute(
                    "INSERT INTO samples VALUES (?,?,?,?)",
                    (sample_id, run_id, task, replicate),
                )
        ledger._event("run_created", run_id=run_id, manifest=manifest)
    return run_id, manifest


def test_archived_run_reports_original_identity_and_blocks_score(ledger, protocol):
    run_id, recorded = archived_run(ledger, protocol)
    interpreted = ledger.protocol(run_id).digest
    assert recorded != interpreted
    assert ledger.verify()["integrity"] == "verified"

    summary = ledger.summary(run_id)
    assert summary["protocol_digest"] == recorded
    assert summary["interpreted_protocol_digest"] == interpreted
    assert "protocol_serialization_drift" in summary["score_blockers"]
    assert summary["pass_at_1"] is None


def test_archived_run_cannot_start_new_dispatch(ledger, protocol, task):
    run_id, _ = archived_run(ledger, protocol)
    sample_id = ledger.samples(run_id)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    with pytest.raises(StateError, match="protocol serialization drift"):
        ledger.begin_attempt(sample_id, request)
    assert ledger.verify()["events"] == 1


def test_validate_protocol_distinguishes_raw_and_interpreted_digest(
    tmp_path, protocol, monkeypatch, capsys
):
    raw = legacy_manifest(protocol)
    path = tmp_path / "historical-protocol.json"
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["graybench", "validate-protocol", str(path)])

    main()

    result = json.loads(capsys.readouterr().out)
    assert result["protocol_digest"] == identity(raw)
    assert result["interpreted_protocol_digest"] != result["protocol_digest"]
    assert result["serialization_stable"] is False

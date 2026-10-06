import hashlib

import httpx
import pytest

from graybench.contracts import Generation
from graybench.identity import canonical, identity
from graybench.ledger import StateError
from graybench.providers import Ollama
from graybench.transport import Transport


def run_with_answer(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(protocol.model, task, None))
    ledger.finish_attempt(
        attempt,
        "returned",
        {},
        200,
        Generation(
            text="original",
            returned_model=protocol.model.model,
            response_id=None,
            finish_reason="stop",
            usage={},
        ),
    )
    return run, sample


def rechain(ledger, events):
    # Simulate a consistently rehashed, but semantically invalid, local event log.
    ledger.db.execute("DROP TRIGGER immutable_events_UPDATE")
    previous = "0" * 64
    for seq, event in enumerate(events, 1):
        payload = ledger._blob(event)
        digest = identity({"seq": seq, "previous": previous, "payload": payload})
        ledger.db.execute(
            "UPDATE events SET previous=?,digest=?,payload=? WHERE seq=?",
            (previous, digest, payload, seq),
        )
        previous = digest


def events(ledger):
    return [
        ledger.blob(row[0]) for row in ledger.db.execute("SELECT payload FROM events ORDER BY seq")
    ]


def test_generation_content_is_bound_even_when_replacement_blob_has_valid_hash(
    ledger, protocol, task
):
    _, sample = run_with_answer(ledger, protocol, task)
    original = ledger.db.execute(
        "SELECT content FROM generations WHERE sample_id=?", (sample,)
    ).fetchone()[0]
    replacement = {**ledger.blob(original), "text": "changed answer"}
    digest = ledger._blob(replacement)
    ledger.db.execute("DROP TRIGGER immutable_generations_UPDATE")
    ledger.db.execute("UPDATE generations SET content=? WHERE sample_id=?", (digest, sample))
    with pytest.raises(StateError, match="row binding mismatch"):
        ledger.verify()


def test_unrecorded_pass_cannot_become_a_summary_score(ledger, protocol, task):
    run, sample = run_with_answer(ledger, protocol, task)
    ledger.db.execute(
        "INSERT INTO judgments VALUES (?,?,?,?)",
        (sample, protocol.judge_digest, "pass", ledger._blob({})),
    )
    with pytest.raises(StateError, match="Missing or duplicate event binding for judgments"):
        ledger.summary(run)


def test_duplicate_recorded_event_is_rejected(ledger, protocol, task):
    _, sample = run_with_answer(ledger, protocol, task)
    ledger.judge(sample, protocol.judge_digest, "pass", {})
    ledger._event(
        "judgment_recorded",
        sample_id=sample,
        judge_digest=protocol.judge_digest,
        outcome="pass",
        evidence=ledger._blob({}),
    )
    with pytest.raises(StateError, match="duplicate event binding"):
        ledger.verify()


def test_rehashed_judgment_before_return_is_rejected(ledger, protocol, task):
    _, sample = run_with_answer(ledger, protocol, task)
    ledger.judge(sample, protocol.judge_digest, "pass", {})
    records = events(ledger)
    records[2], records[3] = records[3], records[2]
    rechain(ledger, records)
    with pytest.raises(StateError, match="Judgment precedes"):
        ledger.verify()


def test_legacy_events_are_not_retroactively_attested(ledger, protocol, task):
    run_with_answer(ledger, protocol, task)
    records = events(ledger)
    for record in records:
        record.pop("records")
    rechain(ledger, records)
    with pytest.raises(StateError, match="Legacy event lacks exact row bindings"):
        ledger.verify()
    assert not ledger.db.in_transaction


def test_delivery_timestamps_are_bound(ledger, protocol, task):
    run_with_answer(ledger, protocol, task)
    ledger.db.execute("DROP TRIGGER immutable_deliveries_UPDATE")
    ledger.db.execute("UPDATE deliveries SET finished_at='2000-01-01T00:00:00+00:00'")
    with pytest.raises(StateError, match="row binding mismatch"):
        ledger.verify()


@pytest.mark.parametrize("tampered", [b'{"a":1,"a":1}', b'{ "a": 1 }'])
def test_noncanonical_blob_bytes_are_rejected_even_if_parsed_digest_matches(ledger, tampered):
    digest = ledger._blob({"a": 1})
    ledger.db.execute("DROP TRIGGER immutable_blobs_UPDATE")
    ledger.db.execute("UPDATE blobs SET content=? WHERE digest=?", (tampered, digest))
    with pytest.raises(StateError, match="canonical"):
        ledger.verify()


def bound_request_evidence(request, protocol):
    content = canonical(request.body)
    return {
        "request_capture_version": "canonical-body-v1",
        "request_body": request.body,
        "request_content_sha256": hashlib.sha256(content).hexdigest(),
        "request_content_bytes": len(content),
        "path": request.path,
        "method": "POST",
        "base_url": protocol.model.base_url,
        "adapter_code_digest": request.adapter_code_digest,
        "credential_scope_id": protocol.model.credential_scope_id,
        "request_public_headers": request.public_headers,
        "auth_header_names": list(request.credential_header_names),
    }


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("request_body", {"model": "different"}),
        ("request_content_sha256", "0" * 64),
        ("request_content_bytes", 0),
        ("path", "/different"),
        ("base_url", "https://different.example"),
        ("adapter_code_digest", "0" * 64),
        ("credential_scope_id", "different-scope"),
        ("request_public_headers", {"x-extra": "different"}),
        ("auth_header_names", ["authorization"]),
    ],
)
def test_delivery_must_match_frozen_request_when_wire_evidence_is_present(
    ledger, protocol, task, field, replacement
):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    evidence = {**bound_request_evidence(request, protocol), field: replacement}
    with pytest.raises(StateError, match="request evidence"):
        ledger.finish_attempt(attempt, "rejected", evidence, 400)
    assert ledger.dispatch_state(sample)["state"] == "unresolved_delivery"


def test_partial_wire_request_evidence_is_rejected(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    with pytest.raises(StateError, match="request evidence"):
        ledger.finish_attempt(
            attempt,
            "rejected",
            {"request_capture_version": "canonical-body-v1", "request_body": request.body},
            400,
        )


def test_missing_request_binding_is_visible_but_historical_delivery_still_verifies(
    ledger, protocol, task
):
    run, _ = run_with_answer(ledger, protocol, task)
    assert ledger.verify()["integrity"] == "verified"
    report = ledger.summary(run)
    assert report["request_evidence_binding"] == {"bound": 0, "unbound": 1}
    assert "request_evidence_unbound" in report["publication_blockers"]


def test_matching_wire_request_evidence_verifies_and_is_reported_bound(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    ledger.finish_attempt(attempt, "rejected", bound_request_evidence(request, protocol), 400)
    assert ledger.verify()["integrity"] == "verified"
    assert ledger.summary(run)["request_evidence_binding"] == {"bound": 1, "unbound": 0}


def test_transport_request_capture_binds_to_attempt(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    provider = Ollama()
    request = provider.prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(400)))
    transport = Transport(protocol.model, client=client)
    try:
        delivery = transport.generate(request, provider)
    finally:
        client.close()
    assert delivery.kind == "rejected"
    assert delivery.evidence["request_capture_version"] == "canonical-body-v1"
    ledger.finish_attempt(attempt, delivery.kind, delivery.evidence, delivery.status)
    assert ledger.summary(run)["request_evidence_binding"] == {"bound": 1, "unbound": 0}


def test_rechained_request_mismatch_is_rejected_at_verification(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    evidence = bound_request_evidence(request, protocol)
    ledger.finish_attempt(attempt, "rejected", evidence, 400)
    assert ledger.verify()["integrity"] == "verified"
    forged = ledger._blob({**evidence, "path": "/different"})
    ledger.db.execute("DROP TRIGGER immutable_deliveries_UPDATE")
    ledger.db.execute("UPDATE deliveries SET evidence=? WHERE attempt_id=?", (forged, attempt))
    records = events(ledger)
    finish = next(record for record in records if record["kind"] == "attempt_finished")
    finish["evidence"] = forged
    finish["records"]["deliveries"][0]["evidence"] = forged
    rechain(ledger, records)
    with pytest.raises(StateError, match="request evidence"):
        ledger.verify()

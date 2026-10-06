import pytest

from graybench.contracts import Generation
from graybench.identity import identity
from graybench.ledger import StateError
from graybench.providers import Ollama


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

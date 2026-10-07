"""Terminal abandonment preserves the original denominator and cannot repair a score."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from graybench.contracts import Generation
from graybench.ledger import Ledger, StateError
from graybench.providers import Ollama


def api():
    from graybench import run_abandonment

    return run_abandonment


def generation(protocol):
    return Generation(
        text="original",
        returned_model=protocol.model.model,
        response_id=None,
        finish_reason="stop",
        usage={},
    )


def plan(book, run):
    return api().plan_abandonment(
        book,
        run,
        reason="Interrupted run; preserve all evidence",
        workers_stopped=True,
    )


def test_terminal_abandonment_preserves_attempt_and_denominator(ledger, protocol, task):
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    request = Ollama().prepare(protocol.model, task, None)
    attempt = ledger.begin_attempt(sample, request)
    before = dict(ledger.db.execute("SELECT * FROM attempts").fetchone())
    frozen = plan(ledger, run)
    assert frozen.snapshot["pass_at_1"] is None
    result = api().abandon_run(ledger, frozen)
    assert result["state"] == "abandoned"
    assert not result["publication_eligible"]
    summary = ledger.summary(run)
    assert summary["planned_samples"] == 1
    assert summary["pass_at_1"] is None
    assert "run_abandoned" in summary["score_blockers"]
    assert summary["run_abandonment"]["plan_digest"] == frozen.digest
    assert dict(ledger.db.execute("SELECT * FROM attempts").fetchone()) == before
    assert ledger.dispatch_state(sample) == {"state": "abandoned"}
    for action in (
        lambda: ledger.begin_attempt(sample, request),
        lambda: ledger.finish_attempt(attempt, "returned", {}, 200, generation(protocol)),
        lambda: ledger.record_model_observation(run, {"model_spec_digest": protocol.model.digest}),
        lambda: ledger.claim_judgment(sample, protocol.judge_digest),
        lambda: ledger.judge(sample, protocol.judge_digest, "pass", {}),
        lambda: api().abandon_run(ledger, frozen),
    ):
        with pytest.raises(StateError, match="abandon"):
            action()
    ledger.verify()


def test_stale_plan_and_unknown_run_are_refused(ledger, protocol):
    run = ledger.create_run(protocol)
    frozen = plan(ledger, run)
    ledger.create_run(protocol)  # Even another run changes this exact ledger snapshot.
    with pytest.raises(StateError, match="snapshot"):
        api().abandon_run(ledger, frozen)
    assert ledger.abandonment(run) is None
    with pytest.raises(StateError):
        plan(ledger, "0" * 32)
    for field, value in (
        ("method", "repair"),
        ("analysis_source", "0" * 64),
        ("workers_stopped", False),
    ):
        with pytest.raises(ValueError):
            api().abandon_run(ledger, frozen.model_copy(update={field: value}))


@pytest.mark.parametrize("source_drift", [False, True])
def test_complete_run_cannot_be_abandoned(ledger, protocol, task, source_drift):
    if source_drift:
        protocol = protocol.model_copy(update={"analysis_digest": "0" * 64})
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(protocol.model, task, None))
    ledger.finish_attempt(attempt, "returned", {}, 200, generation(protocol))
    ledger.judge(sample, protocol.judge_digest, "pass", {})
    assert ledger.summary(run)["complete"] is not source_drift
    with pytest.raises(StateError, match="complete"):
        plan(ledger, run)


@pytest.mark.parametrize(
    "reason,stopped",
    [("", True), ("  ", True), ("x" * 4097, True), ("reason", False), ("reason", 1)],
)
def test_reason_and_stopped_declaration_are_required(ledger, protocol, reason, stopped):
    run = ledger.create_run(protocol)
    with pytest.raises(ValueError):
        api().plan_abandonment(ledger, run, reason=reason, workers_stopped=stopped)


@pytest.mark.parametrize(
    "boundary", ["intent", "ambiguous", "return", "claim", "missing_post", "missing_post_check"]
)
def test_actual_process_exit_then_terminal_close_preserves_evidence(
    tmp_path,
    protocol,
    task,
    boundary,
):
    api()  # Fail clearly before launching a worker if implementation is absent.
    if boundary in {"missing_post", "missing_post_check"}:
        from graybench.contracts import ModelObservationTiming

        protocol = protocol.model_copy(
            update={"schema_version": "3.3", "model_observation_timing": ModelObservationTiming()}
        )
    path = tmp_path / "crash.sqlite"
    request = Ollama().prepare(protocol.model, task, None)
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import os,sys,json\nfrom pathlib import Path\n"
        "from graybench.ledger import Ledger\n"
        "from graybench.contracts import Protocol,PreparedRequest,Generation\n"
        "config=json.loads(Path(sys.argv[1]).read_text())\n"
        "book=Ledger(Path(config['path']))\n"
        "p=Protocol.model_validate_json(json.dumps(config['protocol']))\n"
        "run=book.create_run(p)\n"
        "sample=book.samples(run)[0]['id']\n"
        "obs={'model_spec_digest':p.model.digest,'identity':{'status':'observed','digest':'a'*64}}\n"
        "pre=book.record_model_observation(run,obs) if p.schema_version=='3.3' else {}\n"
        "attempt=book.begin_attempt(sample,PreparedRequest.model_validate_json("
        "json.dumps(config['request'])),pre_observation_id=pre.get('observation_id'))\n"
        "if config['boundary']=='ambiguous': book.finish_attempt(attempt,'ambiguous',{})\n"
        "if config['boundary'] in ('return','claim','missing_post','missing_post_check'):\n"
        " token=book.finish_attempt(attempt,'returned',{},200,Generation(text='original',"
        "returned_model=p.model.model,response_id=None,finish_reason='stop',usage={}))\n"
        "if config['boundary']=='claim': book.claim_judgment(sample,p.judge_digest)\n"
        "if config['boundary']=='missing_post_check':\n"
        " book.recover_post_observation_check=lambda attempt: os._exit(73)\n"
        " book.record_model_observation(run,obs,attempt_id=attempt,post_token=token)\n"
        "os._exit(73)\n",
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "path": str(path),
                "boundary": boundary,
                "protocol": protocol.model_dump(mode="json"),
                "request": request.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    completed = subprocess.run(
        [sys.executable, str(worker), str(config)], env=env, capture_output=True, timeout=30
    )
    assert completed.returncode == 73, completed.stderr.decode()
    book = Ledger(path)
    try:
        book.verify()
        run = book.db.execute("SELECT id FROM runs").fetchone()[0]
        tables = (
            "attempts",
            "deliveries",
            "generations",
            "judgment_claims",
            "judgments",
            "attempt_observations",
            "post_observation_checks",
        )
        before = {
            table: [dict(row) for row in book.db.execute(f"SELECT * FROM {table}")]
            for table in tables
        }
        if boundary == "missing_post":
            assert book.attempt_observation_status(run)["status"] == "missing_post"
        if boundary == "missing_post_check":
            assert book.attempt_observation_status(run)["status"] == "missing_post_check"
        api().abandon_run(book, plan(book, run))
        assert not book.summary(run)["complete"]
        assert all(
            [dict(row) for row in book.db.execute(f"SELECT * FROM {table}")] == before[table]
            for table in tables
        )
    finally:
        book.close()
    reopened = Ledger(path, readonly=True)
    try:
        assert reopened.summary(run)["run_abandonment"]["state"] == "abandoned"
        reopened.verify()
    finally:
        reopened.close()


def test_cli_freezes_read_only_plan_and_requires_existing_ledger(tmp_path, protocol, monkeypatch):
    from graybench.cli import main

    path, output = tmp_path / "book.sqlite", tmp_path / "abandonment.json"
    book = Ledger(path)
    run = book.create_run(protocol)
    book.close()
    before = path.read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "abandonment-plan",
            str(path),
            run,
            str(output),
            "--reason",
            "Interrupted experiment",
            "--workers-stopped",
        ],
    )
    main()
    assert path.read_bytes() == before
    frozen = api().AbandonmentPlan.model_validate_json(output.read_bytes())
    assert frozen.run_id == run
    with pytest.raises(FileExistsError):
        main()
    monkeypatch.setattr(sys, "argv", ["graybench", "abandon-run", str(path), str(output)])
    main()
    book = Ledger(path, readonly=True)
    try:
        assert book.summary(run)["run_abandonment"]["state"] == "abandoned"
    finally:
        book.close()
    missing = tmp_path / "missing.sqlite"
    monkeypatch.setattr(sys, "argv", ["graybench", "abandon-run", str(missing), str(output)])
    with pytest.raises(StateError, match="exist"):
        main()
    assert not missing.exists()


def test_rehashed_execution_event_after_abandonment_is_rejected(ledger, protocol):
    run = ledger.create_run(protocol)
    api().abandon_run(ledger, plan(ledger, run))
    # Bypass application guards like a corrupt writer, retaining valid row/event hashes.
    with ledger.transaction():
        observation = ledger._blob({"model_spec_digest": protocol.model.digest})
        cursor = ledger.db.execute(
            "INSERT INTO model_observations(run_id,content,recorded_at) VALUES (?,?,?)",
            (run, observation, "2026-10-07T00:00:00Z"),
        )
        ledger._event(
            "model_observed", run_id=run, observation=observation, observation_id=cursor.lastrowid
        )
    with pytest.raises(StateError, match="after run abandonment"):
        ledger.verify()


def test_extra_foreign_sample_cannot_redirect_closed_run_check(ledger, protocol):
    run = ledger.create_run(protocol)
    other = ledger.create_run(protocol)
    api().abandon_run(ledger, plan(ledger, run))
    sample = ledger.samples(other)[0]["id"]
    with ledger.transaction():
        observation = ledger._blob({"model_spec_digest": protocol.model.digest})
        cursor = ledger.db.execute(
            "INSERT INTO model_observations(run_id,content,recorded_at) VALUES (?,?,?)",
            (run, observation, "2026-10-07T00:00:00Z"),
        )
        ledger._event(
            "model_observed",
            run_id=run,
            observation=observation,
            observation_id=cursor.lastrowid,
            sample_id=sample,
        )
    with pytest.raises(StateError, match="after run abandonment"):
        ledger.verify()


def test_unbound_terminal_row_and_mutation_are_rejected(ledger, protocol):
    import sqlite3

    run = ledger.create_run(protocol)
    record = api().abandon_run(ledger, plan(ledger, run))
    for operation in (
        "UPDATE run_abandonments SET recorded_at='changed'",
        "DELETE FROM run_abandonments",
    ):
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            ledger.db.execute(operation)
    # Removing a bound event must not leave an apparently valid terminal record.
    ledger.db.execute("DROP TRIGGER immutable_events_DELETE")
    ledger.db.execute("DELETE FROM events WHERE seq=(SELECT MAX(seq) FROM events)")
    with pytest.raises(StateError, match="binding"):
        ledger.summary(run)
    assert record["publication_eligible"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("planned_samples", 999),
        ("returned_samples", 1),
        ("judged_samples", 1),
        ("run_id", "0" * 32),
    ],
)
def test_rehashed_terminal_snapshot_cannot_invent_counts_or_run(ledger, protocol, field, value):
    from test_ledger_evidence import events, rechain

    from graybench.identity import identity
    from graybench.ledger_evidence import event_records

    run = ledger.create_run(protocol)
    record = api().abandon_run(ledger, plan(ledger, run))
    record["plan"]["snapshot"][field] = value
    record["plan_digest"] = identity(record["plan"])
    content = ledger._blob(record)
    ledger.db.execute("DROP TRIGGER immutable_run_abandonments_UPDATE")
    ledger.db.execute("UPDATE run_abandonments SET content=? WHERE run_id=?", (content, run))
    modified = events(ledger)
    modified[-1]["content"] = content
    modified[-1]["records"] = event_records(ledger.db, modified[-1])
    rechain(ledger, modified)
    with pytest.raises(StateError, match="incomplete prior snapshot"):
        ledger.verify()


def test_only_one_concurrent_close_commits(tmp_path, protocol):
    path = tmp_path / "concurrent.sqlite"
    book = Ledger(path)
    run = book.create_run(protocol)
    frozen = plan(book, run)
    book.close()
    barrier = threading.Barrier(2)
    results = []

    def close_run():
        connection = Ledger(path)
        try:
            barrier.wait(timeout=10)
            try:
                api().abandon_run(connection, frozen)
                results.append("committed")
            except StateError:
                results.append("refused")
        finally:
            connection.close()

    threads = [threading.Thread(target=close_run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive()
    assert sorted(results) == ["committed", "refused"]
    reopened = Ledger(path, readonly=True)
    try:
        reopened.verify()
        assert reopened.db.execute("SELECT COUNT(*) FROM run_abandonments").fetchone()[0] == 1
    finally:
        reopened.close()


@pytest.mark.parametrize("scheduler", ["generation", "judgment", "upstream", "native", "protected"])
def test_terminal_scheduler_stops_before_transport_or_oracle(ledger, protocol, scheduler):
    from graybench.campaign import GenerationRunner
    from graybench.evaluation_campaign import JudgmentRunner, UpstreamCampaign
    from graybench.native_campaign import NativeCampaign
    from graybench.protected_campaign import ProtectedCampaign

    run = ledger.create_run(protocol)
    api().abandon_run(ledger, plan(ledger, run))
    classes = {
        "generation": GenerationRunner,
        "judgment": JudgmentRunner,
        "upstream": UpstreamCampaign,
        "native": NativeCampaign,
        "protected": ProtectedCampaign,
    }
    # Only durable identity is available after process restart. Stopping must precede
    # accesses to a transport, oracle, setup or runtime that no longer exists.
    runner = object.__new__(classes[scheduler])
    runner.ledger, runner.run_id = ledger, run
    if scheduler == "upstream":
        from types import SimpleNamespace

        runner.generations = SimpleNamespace(ledger=ledger, run_id=run)
    assert runner.step() == {"state": "stopped", "reason": "run_abandoned"}


def test_closed_run_refuses_discovery_before_provider_call(ledger, protocol):
    from graybench.model_discovery import observe_run

    run = ledger.create_run(protocol)
    api().abandon_run(ledger, plan(ledger, run))
    with pytest.raises(StateError, match="abandon"):
        observe_run(ledger, run, object())  # No transport is touched.


def test_historical_read_only_database_needs_no_migration(tmp_path, protocol):
    path = tmp_path / "historical.sqlite"
    book = Ledger(path)
    run = book.create_run(protocol)
    before = book.summary(run)
    book.db.execute("DROP TABLE run_abandonments")  # Mimic a pre-feature empty schema.
    book.close()
    historical = Ledger(path, readonly=True)
    try:
        assert historical.summary(run) == before
        frozen = plan(historical, run)
    finally:
        historical.close()
    migrated = Ledger(path)
    try:
        assert migrated.summary(run) == before
        api().abandon_run(migrated, frozen)
        migrated.verify()
    finally:
        migrated.close()

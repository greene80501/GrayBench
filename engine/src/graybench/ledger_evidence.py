"""Exact relational records bound by ledger events; no database writes."""

from collections import Counter
from datetime import datetime, timedelta

from graybench.contracts import Protocol
from graybench.identity import identity

TABLES = (
    "runs",
    "run_contexts",
    "model_observations",
    "attempts",
    "attempt_dispatch_aborts",
    "attempt_observations",
    "deliveries",
    "post_observation_claims",
    "post_observation_checks",
    "generations",
    "judgments",
    "judgment_claims",
)


def event_records(db, event):
    kind = event["kind"]

    def one(table, **where):
        rows = db.execute(
            f"SELECT * FROM {table} WHERE " + " AND ".join(f"{key}=?" for key in where),
            tuple(where.values()),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("Event does not identify exactly one " + table + " record")
        return {table: [dict(rows[0])]}

    if kind == "run_created":
        return one("runs", id=event["run_id"], manifest=event["manifest"])
    if kind == "run_context_recorded":
        return one("run_contexts", run_id=event["run_id"], content=event["context"])
    if kind == "model_observed":
        result = one(
            "model_observations",
            id=event["observation_id"],
            run_id=event["run_id"],
            content=event["observation"],
        )
        if "attempt_id" in event:
            result.update(
                one(
                    "attempt_observations",
                    attempt_id=event["attempt_id"],
                    phase="post",
                    observation_id=event["observation_id"],
                )
            )
        return result
    if kind == "attempt_started":
        result = one(
            "attempts",
            id=event["attempt_id"],
            sample_id=event["sample_id"],
            request=event["request"],
        )
        if "pre_observation_id" in event:
            result.update(
                one(
                    "attempt_observations",
                    attempt_id=event["attempt_id"],
                    phase="pre",
                    observation_id=event["pre_observation_id"],
                )
            )
        return result
    if kind == "attempt_dispatch_aborted":
        return one("attempt_dispatch_aborts", attempt_id=event["attempt_id"])
    if kind == "post_observation_checked":
        return one("post_observation_checks", attempt_id=event["attempt_id"])
    if kind == "attempt_finished":
        result = one(
            "deliveries",
            attempt_id=event["attempt_id"],
            kind=event["delivery"],
            evidence=event["evidence"],
        )
        claim = db.execute(
            "SELECT * FROM post_observation_claims WHERE attempt_id=?",
            (event["attempt_id"],),
        ).fetchone()
        if claim is not None:
            result["post_observation_claims"] = [dict(claim)]
        generations = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM generations WHERE attempt_id=?", (event["attempt_id"],)
            )
        ]
        if len(generations) != int(event["delivery"] == "returned"):
            raise ValueError("Delivery and saved generation disagree")
        result["generations"] = generations
        return result
    if kind == "judgment_recorded":
        return one(
            "judgments",
            sample_id=event["sample_id"],
            judge_digest=event["judge_digest"],
            outcome=event["outcome"],
            evidence=event["evidence"],
        )
    if kind == "judgment_started":
        return one(
            "judgment_claims", sample_id=event["sample_id"], judge_digest=event["judge_digest"]
        )
    raise ValueError("Unknown ledger event kind")


def verify_records(db, events):
    observed = {table: Counter() for table in TABLES}
    runs, attempts, returned, claimed, aborted, post_observed, post_checked = (
        set(),
        set(),
        set(),
        set(),
        set(),
        set(),
        set(),
    )
    finished, latest, latest_observation = {}, {}, {}
    ordinals = Counter()
    samples = {row["id"]: dict(row) for row in db.execute("SELECT * FROM samples")}
    protocols = {
        row["id"]: Protocol.model_validate_json(row["content"])
        for row in db.execute(
            "SELECT r.id,b.content FROM runs r JOIN blobs b ON r.manifest=b.digest"
        )
    }
    all_claims = {
        (row["sample_id"], row["judge_digest"])
        for row in db.execute("SELECT * FROM judgment_claims")
    }
    for event in events:
        if "records" not in event:
            raise ValueError("Legacy event lacks exact row bindings; use its original engine")
        records = event_records(db, event)
        if records != event["records"]:
            raise ValueError("Event row binding mismatch")
        kind = event["kind"]
        if kind == "run_created":
            runs.add(event["run_id"])
        elif kind == "model_observed":
            if event["run_id"] not in runs:
                raise ValueError("Model observation precedes run creation")
            if "attempt_id" in event:
                attempt_id = event["attempt_id"]
                if attempt_id not in finished:
                    raise ValueError("Post observation precedes delivery")
                attempt = db.execute(
                    "SELECT s.run_id FROM attempts a JOIN samples s ON s.id=a.sample_id "
                    "WHERE a.id=?",
                    (attempt_id,),
                ).fetchone()
                if attempt is None or attempt["run_id"] != event["run_id"]:
                    raise ValueError("Post observation belongs to another run")
                if protocols[event["run_id"]].schema_version not in {"3.2", "3.3"}:
                    raise ValueError("Post binding requires protocol 3.2+")
                post_observed.add(attempt_id)
            latest_observation[event["run_id"]] = event["observation_id"]
        elif kind == "post_observation_checked":
            attempt_id = event["attempt_id"]
            attempt = db.execute(
                "SELECT s.run_id FROM attempts a JOIN samples s ON s.id=a.sample_id WHERE a.id=?",
                (attempt_id,),
            ).fetchone()
            if (
                attempt_id not in post_observed
                or attempt_id in post_checked
                or attempt is None
                or protocols[attempt["run_id"]].schema_version != "3.3"
            ):
                raise ValueError("Post check does not follow a protocol 3.3 observation")
            check = records["post_observation_checks"][0]
            committed_gap = (
                datetime.fromisoformat(check["checked_at"])
                - datetime.fromisoformat(finished[attempt_id]["finished_at"])
            ).total_seconds()
            if abs(committed_gap - check["gap_seconds"]) > 1e-6:
                raise ValueError("Post check gap disagrees with bound timestamps")
            post_checked.add(attempt_id)
        elif kind == "attempt_started":
            row = records["attempts"][0]
            sample = samples[row["sample_id"]]
            protocol = protocols[sample["run_id"]]
            if sample["run_id"] not in runs:
                raise ValueError("Attempt precedes run creation")
            if protocol.schema_version in {"3.2", "3.3"}:
                if event.get("pre_observation_id") != latest_observation.get(sample["run_id"]):
                    raise ValueError("Attempt pre-observation is not the latest observed identity")
                if "attempt_observations" not in records:
                    raise ValueError("Protocol 3.2+ attempt lacks a pre-observation binding")
            elif "pre_observation_id" in event:
                raise ValueError("Protocol 3.1 attempt cannot bind a 3.2 pre-observation")
            if (
                sample["task_key"] not in protocol.task_keys
                or sample["replicate"] >= protocol.repeats
                or sample["id"]
                != identity([sample["run_id"], sample["task_key"], sample["replicate"]])
                or row["request"] != protocol.request_digests[sample["task_key"]]
            ):
                raise ValueError("Attempt does not match frozen schedule/request")
            ordinals[row["sample_id"]] += 1
            if (
                row["ordinal"] != ordinals[row["sample_id"]]
                or row["ordinal"] > protocol.retry.max_attempts
            ):
                raise ValueError("Attempt ordinals disagree with event order")
            prior_id = latest.get(row["sample_id"])
            if prior_id is not None:
                prior = finished.get(prior_id)
                if (
                    prior is None
                    or prior["kind"] != "rejected"
                    or prior["http_status"] not in protocol.retry.statuses
                ):
                    raise ValueError("Retry follows unresolved or ineligible delivery")
                ready = datetime.fromisoformat(prior["finished_at"]) + timedelta(
                    seconds=protocol.retry.delays_seconds[row["ordinal"] - 2]
                )
                if datetime.fromisoformat(row["started_at"]) < ready:
                    raise ValueError("Retry precedes frozen backoff deadline")
            attempts.add(row["id"])
            latest[row["sample_id"]] = row["id"]
        elif kind == "attempt_dispatch_aborted":
            attempt_id = event["attempt_id"]
            attempt = db.execute(
                "SELECT s.run_id FROM attempts a JOIN samples s ON s.id=a.sample_id WHERE a.id=?",
                (attempt_id,),
            ).fetchone()
            if (
                attempt_id not in attempts
                or attempt_id in finished
                or attempt_id in aborted
                or attempt is None
                or protocols[attempt["run_id"]].schema_version != "3.3"
            ):
                raise ValueError("Dispatch timing abort does not follow a protocol 3.3 attempt")
            aborted.add(attempt_id)
        elif kind == "attempt_finished":
            if event["attempt_id"] not in attempts or event["attempt_id"] in aborted:
                raise ValueError("Delivery precedes dispatch intent")
            attempt = db.execute(
                "SELECT s.run_id FROM attempts a JOIN samples s ON s.id=a.sample_id WHERE a.id=?",
                (event["attempt_id"],),
            ).fetchone()
            expects_claim = protocols[attempt["run_id"]].schema_version in {"3.2", "3.3"}
            if ("post_observation_claims" in records) != expects_claim:
                raise ValueError("Post-observation claim disagrees with protocol version")
            finished[event["attempt_id"]] = records["deliveries"][0]
            returned.update(row["sample_id"] for row in records["generations"])
        elif kind in ("judgment_started", "judgment_recorded"):
            key = (event["sample_id"], event["judge_digest"])
            if event["sample_id"] not in returned:
                raise ValueError("Judgment precedes a returned generation")
            if kind == "judgment_started":
                claimed.add(key)
            elif key in all_claims and key not in claimed:
                raise ValueError("Judgment precedes its durable claim")
        for table, rows in records.items():
            observed[table].update(identity(row) for row in rows)
    for table in TABLES:
        expected = Counter(identity(dict(row)) for row in db.execute(f"SELECT * FROM {table}"))
        if observed[table] != expected:
            raise ValueError("Missing or duplicate event binding for " + table)
    return {"status": "verified", "tables": list(TABLES), "version": 1}

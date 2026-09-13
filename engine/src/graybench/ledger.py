"""Append-only experiment ledger. A transport retry never becomes another model sample.

SQLite constraints protect against programming mistakes, not a malicious database owner.
Exported chain heads must be anchored outside the execution worker for release provenance.
"""

import contextlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from graybench.contracts import Generation, PreparedRequest, Protocol
from graybench.identity import canonical, identity


class StateError(ValueError):
    pass


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS blobs (
 digest TEXT PRIMARY KEY, content BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, manifest TEXT NOT NULL REFERENCES blobs(digest), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 task_key TEXT NOT NULL, replicate INTEGER NOT NULL CHECK(replicate>=0),
 UNIQUE(run_id, task_key, replicate)
);
CREATE TABLE IF NOT EXISTS run_contexts (
 run_id TEXT PRIMARY KEY REFERENCES runs(id), content TEXT NOT NULL REFERENCES blobs(digest)
);
CREATE TABLE IF NOT EXISTS model_observations (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 content TEXT NOT NULL REFERENCES blobs(digest), recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempts (
 id TEXT PRIMARY KEY, sample_id TEXT NOT NULL REFERENCES samples(id),
 ordinal INTEGER NOT NULL CHECK(ordinal>=1), request TEXT NOT NULL REFERENCES blobs(digest),
 started_at TEXT NOT NULL, UNIQUE(sample_id, ordinal), UNIQUE(id, sample_id)
);
CREATE TABLE IF NOT EXISTS deliveries (
 attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
 kind TEXT NOT NULL CHECK(kind IN ('returned','rejected','ambiguous')),
 http_status INTEGER, evidence TEXT NOT NULL REFERENCES blobs(digest), finished_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS generations (
 sample_id TEXT PRIMARY KEY REFERENCES samples(id), attempt_id TEXT NOT NULL UNIQUE,
 content TEXT NOT NULL REFERENCES blobs(digest),
 FOREIGN KEY(attempt_id, sample_id) REFERENCES attempts(id, sample_id)
);
CREATE TABLE IF NOT EXISTS judgments (
 sample_id TEXT NOT NULL REFERENCES generations(sample_id), judge_digest TEXT NOT NULL,
 outcome TEXT NOT NULL CHECK(outcome IN
 ('pass','fail','candidate_error','timeout','unsupported','infrastructure_error')),
 evidence TEXT NOT NULL REFERENCES blobs(digest),
 PRIMARY KEY(sample_id, judge_digest)
);
CREATE TABLE IF NOT EXISTS judgment_claims (
 sample_id TEXT NOT NULL REFERENCES generations(sample_id), judge_digest TEXT NOT NULL,
 started_at TEXT NOT NULL, PRIMARY KEY(sample_id, judge_digest)
);
CREATE TABLE IF NOT EXISTS events (
 seq INTEGER PRIMARY KEY, previous TEXT NOT NULL, digest TEXT NOT NULL UNIQUE,
 payload TEXT NOT NULL REFERENCES blobs(digest)
);
"""


def now() -> str:
    return datetime.now(UTC).isoformat()


class Ledger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        for table in (
            "blobs",
            "runs",
            "run_contexts",
            "model_observations",
            "samples",
            "attempts",
            "deliveries",
            "generations",
            "judgments",
            "judgment_claims",
            "events",
        ):
            for operation in ("UPDATE", "DELETE"):
                self.db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation} "
                    f"BEFORE {operation} ON {table} BEGIN "
                    "SELECT RAISE(ABORT, 'append-only ledger'); END"
                )

    def close(self) -> None:
        self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _blob(self, value: Any) -> str:
        digest = identity(value)
        self.db.execute("INSERT OR IGNORE INTO blobs VALUES (?,?)", (digest, canonical(value)))
        return digest

    def blob(self, digest: str) -> Any:
        row = self.db.execute("SELECT content FROM blobs WHERE digest=?", (digest,)).fetchone()
        if not row:
            raise StateError("Missing artifact")
        value = json.loads(row[0])
        if identity(value) != digest:
            raise StateError("Artifact digest mismatch")
        return value

    def _event(self, kind: str, **data: Any) -> None:
        row = self.db.execute("SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (row[0] + 1, row[1]) if row else (1, "0" * 64)
        payload = self._blob({"kind": kind, "at": now(), **data})
        digest = identity({"seq": seq, "previous": previous, "payload": payload})
        self.db.execute("INSERT INTO events VALUES (?,?,?,?)", (seq, previous, digest, payload))

    def create_run(self, protocol: Protocol, context: dict | None = None) -> str:
        run_id = uuid.uuid4().hex
        with self.transaction():
            manifest = self._blob(protocol.model_dump(mode="json"))
            self.db.execute("INSERT INTO runs VALUES (?,?,?)", (run_id, manifest, now()))
            if context is not None:
                artifact = self._blob(context)
                self.db.execute("INSERT INTO run_contexts VALUES (?,?)", (run_id, artifact))
                self._event("run_context_recorded", run_id=run_id, context=artifact)
            for task in protocol.task_keys:
                for replicate in range(protocol.repeats):
                    sample = identity([run_id, task, replicate])
                    self.db.execute(
                        "INSERT INTO samples VALUES (?,?,?,?)", (sample, run_id, task, replicate)
                    )
            self._event("run_created", run_id=run_id, manifest=manifest)
        return run_id

    def context(self, run_id: str) -> dict:
        row = self.db.execute(
            "SELECT content FROM run_contexts WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise StateError("Run has no frozen execution context")
        return self.blob(row[0])

    def record_model_observation(self, run_id: str, observation: dict) -> dict:
        if observation.get("model_spec_digest") != self.protocol(run_id).model.digest:
            raise StateError("Discovery observation belongs to a different model specification")
        with self.transaction():
            artifact = self._blob(observation)
            self.db.execute(
                "INSERT INTO model_observations(run_id,content,recorded_at) VALUES (?,?,?)",
                (run_id, artifact, now()),
            )
            self._event("model_observed", run_id=run_id, observation=artifact)
        return self.discovery_status(run_id)

    def discovery_status(self, run_id: str) -> dict:
        records = [
            self.blob(row[0])
            for row in self.db.execute(
                "SELECT content FROM model_observations WHERE run_id=? ORDER BY id", (run_id,)
            )
        ]
        if not records:
            return {"status": "not_observed"}
        identities = [record["identity"] for record in records]
        if any(i["status"] != "observed" for i in identities):
            return {
                "status": "unresolved",
                "reason": "identity unavailable",
                "observations": len(records),
            }
        if len({i["digest"] for i in identities}) != 1:
            return {
                "status": "unresolved",
                "reason": "discovery identity changed",
                "observations": len(records),
            }
        return {
            "status": "stable_observed",
            "observations": len(records),
            "digest": identities[0]["digest"],
        }

    def protocol(self, run_id: str) -> Protocol:
        row = self.db.execute("SELECT manifest FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise StateError("Unknown run")
        return Protocol.model_validate_json(canonical(self.blob(row[0])))

    def samples(self, run_id: str) -> list[dict]:
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM samples WHERE run_id=? ORDER BY task_key,replicate", (run_id,)
            )
        ]

    def begin_attempt(self, sample_id: str, request: PreparedRequest) -> str:
        """Commit dispatch intent before touching the network. Pending delivery stops resume."""
        with self.transaction():
            sample = self.db.execute("SELECT * FROM samples WHERE id=?", (sample_id,)).fetchone()
            if not sample:
                raise StateError("Unscheduled sample")
            protocol = self.protocol(sample["run_id"])
            if self.model_identity(sample["run_id"])["status"] == "unresolved":
                raise StateError("Returned model identity requires adjudication")
            if self.discovery_status(sample["run_id"])["status"] == "unresolved":
                raise StateError("Model discovery requires adjudication")
            if request.model != protocol.model.model or request.adapter != protocol.model.adapter:
                raise StateError("Request does not match frozen model identity")
            if self.db.execute(
                "SELECT 1 FROM generations WHERE sample_id=?", (sample_id,)
            ).fetchone():
                raise StateError("A returned answer cannot be replaced")
            prior = self.db.execute(
                "SELECT a.*,d.kind,d.http_status,d.finished_at FROM attempts a "
                "LEFT JOIN deliveries d "
                "ON a.id=d.attempt_id WHERE a.sample_id=? ORDER BY ordinal DESC LIMIT 1",
                (sample_id,),
            ).fetchone()
            ordinal = 1
            if prior:
                if (
                    prior["kind"] != "rejected"
                    or prior["http_status"] not in protocol.retry.statuses
                ):
                    raise StateError("Previous delivery is not eligible for retry")
                if prior["request"] != request.digest:
                    raise StateError("Retry must use identical public request")
                ordinal = prior["ordinal"] + 1
            if ordinal > protocol.retry.max_attempts:
                raise StateError("Frozen retry budget exhausted")
            if prior:
                ready = datetime.fromisoformat(prior["finished_at"]) + timedelta(
                    seconds=protocol.retry.delays_seconds[ordinal - 2]
                )
                if datetime.fromisoformat(now()) < ready:
                    raise StateError("Frozen retry backoff has not elapsed")
            if request.digest != protocol.request_digests[sample["task_key"]]:
                raise StateError("Request differs from the frozen experiment")
            attempt_id = uuid.uuid4().hex
            request_id = self._blob(request.model_dump(mode="json"))
            self.db.execute(
                "INSERT INTO attempts VALUES (?,?,?,?,?)",
                (attempt_id, sample_id, ordinal, request_id, now()),
            )
            self._event(
                "attempt_started", attempt_id=attempt_id, sample_id=sample_id, request=request_id
            )
        return attempt_id

    def dispatch_state(self, sample_id: str) -> dict:
        sample = self.db.execute("SELECT * FROM samples WHERE id=?", (sample_id,)).fetchone()
        if sample is None:
            raise StateError("Unscheduled sample")
        if self.db.execute("SELECT 1 FROM generations WHERE sample_id=?", (sample_id,)).fetchone():
            return {"state": "returned"}
        prior = self.db.execute(
            "SELECT a.ordinal,d.kind,d.http_status,d.finished_at FROM attempts a "
            "LEFT JOIN deliveries d ON a.id=d.attempt_id WHERE a.sample_id=? "
            "ORDER BY a.ordinal DESC LIMIT 1",
            (sample_id,),
        ).fetchone()
        if prior is None:
            return {"state": "ready"}
        if prior["kind"] is None or prior["kind"] == "ambiguous":
            return {"state": "unresolved_delivery"}
        policy = self.protocol(sample["run_id"]).retry
        if prior["http_status"] not in policy.statuses or prior["ordinal"] >= policy.max_attempts:
            return {"state": "exhausted"}
        ready = datetime.fromisoformat(prior["finished_at"]) + timedelta(
            seconds=policy.delays_seconds[prior["ordinal"] - 1]
        )
        return {
            "state": "ready" if datetime.fromisoformat(now()) >= ready else "deferred",
            "not_before": ready.isoformat(),
        }

    def finish_attempt(
        self,
        attempt_id: str,
        kind: str,
        evidence: dict,
        http_status: int | None = None,
        generation: Generation | None = None,
    ) -> None:
        if (kind == "returned") != (generation is not None):
            raise StateError("Returned delivery requires exactly one normalized generation")
        if kind == "returned" and (http_status is None or not 200 <= http_status < 300):
            raise StateError("Returned generation requires successful HTTP delivery")
        if kind == "rejected" and (http_status is None or http_status < 400):
            raise StateError("Rejection requires an explicit HTTP error")
        with self.transaction():
            attempt = self.db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
            if not attempt:
                raise StateError("Unknown attempt")
            artifact = self._blob(evidence)
            self.db.execute(
                "INSERT INTO deliveries VALUES (?,?,?,?,?)",
                (attempt_id, kind, http_status, artifact, now()),
            )
            if generation is not None:
                content = self._blob(generation.model_dump(mode="json"))
                self.db.execute(
                    "INSERT INTO generations VALUES (?,?,?)",
                    (attempt["sample_id"], attempt_id, content),
                )
            self._event("attempt_finished", attempt_id=attempt_id, delivery=kind, evidence=artifact)

    def judge(self, sample_id: str, judge_digest: str, outcome: str, evidence: dict) -> None:
        if len(judge_digest) != 64 or any(c not in "0123456789abcdef" for c in judge_digest):
            raise StateError("Judge must have a content identity")
        with self.transaction():
            artifact = self._blob(evidence)
            self.db.execute(
                "INSERT INTO judgments VALUES (?,?,?,?)",
                (sample_id, judge_digest, outcome, artifact),
            )
            self._event(
                "judgment_recorded",
                sample_id=sample_id,
                judge_digest=judge_digest,
                outcome=outcome,
                evidence=artifact,
            )

    def claim_judgment(self, sample_id: str, judge_digest: str) -> None:
        """Persist evaluation intent; an interrupted oracle is never silently rerolled."""
        if len(judge_digest) != 64 or any(c not in "0123456789abcdef" for c in judge_digest):
            raise StateError("Judge must have a content identity")
        with self.transaction():
            if self.db.execute(
                "SELECT 1 FROM judgments WHERE sample_id=? AND judge_digest=?",
                (sample_id, judge_digest),
            ).fetchone():
                raise StateError("Judgment already recorded")
            self.db.execute(
                "INSERT INTO judgment_claims VALUES (?,?,?)", (sample_id, judge_digest, now())
            )
            self._event("judgment_started", sample_id=sample_id, judge_digest=judge_digest)

    def verify(self) -> dict:
        for row in self.db.execute("SELECT digest FROM blobs"):
            self.blob(row[0])
        previous, count = "0" * 64, 0
        for row in self.db.execute("SELECT * FROM events ORDER BY seq"):
            count += 1
            expected = identity({"seq": count, "previous": previous, "payload": row["payload"]})
            if row["seq"] != count or row["previous"] != previous or row["digest"] != expected:
                raise StateError("Event chain is corrupt")
            previous = expected
        if self.db.execute("PRAGMA foreign_key_check").fetchone():
            raise StateError("Broken ledger relationship")
        return {
            "events": count,
            "chain_head": previous,
            "integrity": "verified",
            "external_anchor": "not_checked",
        }

    def summary(self, run_id: str) -> dict:
        protocol = self.protocol(run_id)
        rows = self.db.execute(
            "SELECT s.task_key,s.replicate,g.content,j.outcome FROM samples s "
            "LEFT JOIN generations g ON s.id=g.sample_id "
            "LEFT JOIN judgments j ON j.sample_id=s.id AND j.judge_digest=? WHERE s.run_id=?",
            (protocol.judge_digest, run_id),
        ).fetchall()
        outcomes = [r["outcome"] for r in rows]
        # Unknown capability or infrastructure is never silently counted as a model failure.
        complete = bool(rows) and all(
            o in {"pass", "fail", "candidate_error", "timeout"} for o in outcomes
        )
        model_identity = self.model_identity(run_id)
        complete = complete and model_identity["status"] != "unresolved"
        discovery = self.discovery_status(run_id)
        complete = complete and discovery["status"] != "unresolved"
        return {
            "run_id": run_id,
            "protocol_digest": protocol.digest,
            "track": protocol.track,
            "planned_samples": len(rows),
            "returned_samples": sum(r["content"] is not None for r in rows),
            "judged_samples": sum(o is not None for o in outcomes),
            "complete": complete,
            "passes": outcomes.count("pass"),
            "pass_at_1": outcomes.count("pass") / len(rows) if complete else None,
            "certification": "not_certified",
            "model_identity": model_identity,
            "model_discovery": discovery,
        }

    def model_identity(self, run_id: str) -> dict:
        spec = self.protocol(run_id).model
        accepted = set(spec.accepted_returned_models or (spec.model,))
        returned = [
            self.blob(row[0])["returned_model"]
            for row in self.db.execute(
                "SELECT g.content FROM generations g JOIN samples s ON s.id=g.sample_id "
                "WHERE s.run_id=?",
                (run_id,),
            )
        ]
        missing = sum(name is None or name == "" for name in returned)
        mismatched = sum(name not in accepted and name not in (None, "") for name in returned)
        return {
            "status": "unresolved"
            if missing or mismatched
            else ("matched_declared_names" if returned else "not_observed"),
            "accepted_names": sorted(accepted),
            "observed_names": sorted(set(n for n in returned if n)),
            "missing": missing,
            "mismatched": mismatched,
            "weights_identity": "not_verified",
        }

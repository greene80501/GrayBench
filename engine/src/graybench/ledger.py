"""Append-only experiment ledger. A transport retry never becomes another model sample.

SQLite constraints protect against programming mistakes, not a malicious database owner.
Exported chain heads must be anchored outside the execution worker for release provenance.
"""

import contextlib
import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from graybench.capability_probe import CapabilityProbe, verify_probe_bundle
from graybench.contracts import (
    Generation,
    ModelSpec,
    PreparedRequest,
    Protocol,
    reject_model_credential,
    require_credential_scope_for_new_run,
)
from graybench.identity import canonical, identity
from graybench.judgment_evidence import campaign_judgment_binding
from graybench.ledger_evidence import event_records, verify_records
from graybench.provenance import source_manifest
from graybench.providers import adapter
from graybench.request_evidence import request_evidence_binding


class StateError(ValueError):
    pass


def _probe_artifact_status(protocol: Protocol, setup: dict | None) -> str:
    profile = protocol.model.capability_profile
    if profile is None or not profile.probe_digests:
        if type(setup) is dict and setup.get("capability_probes"):
            return "unexpected_records"
        return "no_probe_claims"
    if type(setup) is not dict or setup.get("protocol") != protocol.model_dump(mode="json"):
        return "missing_or_invalid"
    try:
        records = tuple(
            CapabilityProbe.model_validate_json(canonical(value))
            for value in setup.get("capability_probes", ())
        )
        verify_probe_bundle(protocol.model, records, adapter(protocol.model.adapter))
    except (ValueError, TypeError, KeyError):
        return "missing_or_invalid"
    return "verified_local_records"


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
CREATE TABLE IF NOT EXISTS attempt_dispatch_aborts (
 attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
 recorded_at TEXT NOT NULL, pre_age_seconds REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS attempt_observations (
 attempt_id TEXT NOT NULL REFERENCES attempts(id),
 phase TEXT NOT NULL CHECK(phase IN ('pre','post')),
 observation_id INTEGER NOT NULL UNIQUE REFERENCES model_observations(id),
 PRIMARY KEY(attempt_id, phase)
);
CREATE TABLE IF NOT EXISTS deliveries (
 attempt_id TEXT PRIMARY KEY REFERENCES attempts(id),
 kind TEXT NOT NULL CHECK(kind IN ('returned','rejected','ambiguous')),
 http_status INTEGER, evidence TEXT NOT NULL REFERENCES blobs(digest), finished_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS post_observation_claims (
 attempt_id TEXT PRIMARY KEY REFERENCES deliveries(attempt_id),
 token_digest TEXT NOT NULL CHECK(length(token_digest)=64)
);
CREATE TABLE IF NOT EXISTS post_observation_checks (
 attempt_id TEXT PRIMARY KEY REFERENCES deliveries(attempt_id),
 checked_at TEXT NOT NULL, gap_seconds REAL NOT NULL
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
    def __init__(self, path: Path, *, readonly: bool = False):
        if readonly:
            if not path.is_file():
                raise FileNotFoundError(path)
            self.db = sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None, timeout=30
            )
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA query_only=ON")
            return
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
            "attempt_dispatch_aborts",
            "attempt_observations",
            "deliveries",
            "post_observation_claims",
            "post_observation_checks",
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
        try:
            value = json.loads(row[0])
            canonical_bytes = canonical(value)
        except (TypeError, ValueError) as exc:
            raise StateError("Artifact JSON is invalid") from exc
        if canonical_bytes != row[0]:
            raise StateError("Artifact JSON is not canonical")
        if identity(value) != digest:
            raise StateError("Artifact digest mismatch")
        return value

    def _event(self, kind: str, **data: Any) -> None:
        row = self.db.execute("SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (row[0] + 1, row[1]) if row else (1, "0" * 64)
        event = {"kind": kind, "at": now(), **data}
        event["records"] = event_records(self.db, event)
        payload = self._blob(event)
        digest = identity({"seq": seq, "previous": previous, "payload": payload})
        self.db.execute("INSERT INTO events VALUES (?,?,?,?)", (seq, previous, digest, payload))

    def create_run(self, protocol: Protocol, context: dict | None = None) -> str:
        if protocol.model.capability_profile is not None:
            ModelSpec.model_validate_json(protocol.model.model_dump_json())
        probe_status = _probe_artifact_status(
            protocol,
            context.get("setup") if type(context) is dict else None,
        )
        if probe_status not in {"no_probe_claims", "verified_local_records"}:
            raise StateError("Capability probe artifacts are missing or invalid")
        require_credential_scope_for_new_run(protocol.model, system_prompt=protocol.system_prompt)
        reject_model_credential(protocol.model, protocol.model_dump(mode="json"), "protocol")
        reject_model_credential(protocol.model, context, "run context")
        if protocol.track in {"qhe-pinned-native-v1", "graybench-protected-semantic-v1"} and (
            protocol.retry.max_attempts != 1
            or protocol.retry.statuses
            or protocol.retry.delays_seconds
        ):
            raise StateError("New dual-track runs require a frozen single dispatch policy")
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

    def record_model_observation(
        self,
        run_id: str,
        observation: dict,
        *,
        attempt_id: str | None = None,
        post_token: str | None = None,
    ) -> dict:
        protocol = self.protocol(run_id)
        self.require_protocol_serialization_stable(run_id, protocol)
        if observation.get("model_spec_digest") != protocol.model.digest:
            raise StateError("Discovery observation belongs to a different model specification")
        reject_model_credential(protocol.model, observation, "model observation")
        with self.transaction():
            if attempt_id is not None:
                attempt = self.db.execute(
                    "SELECT s.run_id,d.attempt_id AS delivered FROM attempts a "
                    "JOIN samples s ON s.id=a.sample_id "
                    "LEFT JOIN deliveries d ON d.attempt_id=a.id WHERE a.id=?",
                    (attempt_id,),
                ).fetchone()
                if attempt is None or attempt["run_id"] != run_id:
                    raise StateError("Post observation belongs to a different run or attempt")
                if (
                    self.protocol(run_id).schema_version not in {"3.2", "3.3"}
                    or not attempt["delivered"]
                ):
                    raise StateError("Post observation requires a delivered protocol 3.2+ attempt")
                claim = self.db.execute(
                    "SELECT token_digest FROM post_observation_claims WHERE attempt_id=?",
                    (attempt_id,),
                ).fetchone()
                if (
                    not isinstance(post_token, str)
                    or claim is None
                    or not secrets.compare_digest(
                        hashlib.sha256(post_token.encode()).hexdigest(), claim["token_digest"]
                    )
                ):
                    raise StateError("Missing or invalid live post-observation token")
                if self.db.execute(
                    "SELECT 1 FROM attempt_observations WHERE attempt_id=? AND phase='post'",
                    (attempt_id,),
                ).fetchone():
                    raise StateError("Post observation already bound")
            elif post_token is not None:
                raise StateError("Post-observation token requires an attempt")
            artifact = self._blob(observation)
            inserted = self.db.execute(
                "INSERT INTO model_observations(run_id,content,recorded_at) VALUES (?,?,?)",
                (run_id, artifact, now()),
            )
            if attempt_id is not None:
                self.db.execute(
                    "INSERT INTO attempt_observations VALUES (?,'post',?)",
                    (attempt_id, inserted.lastrowid),
                )
            self._event(
                "model_observed",
                run_id=run_id,
                observation=artifact,
                observation_id=inserted.lastrowid,
                **({"attempt_id": attempt_id} if attempt_id is not None else {}),
            )
        if attempt_id is not None and protocol.schema_version == "3.3":
            self.recover_post_observation_check(attempt_id)
        return {**self.discovery_status(run_id), "observation_id": inserted.lastrowid}

    def recover_post_observation_check(self, attempt_id: str) -> dict:
        """Close a protocol 3.3 post-check gap without repeating provider I/O."""
        with self.transaction():
            row = self.db.execute(
                "SELECT s.run_id,d.finished_at,post.observation_id AS post_id,"
                "check_row.attempt_id AS checked_id "
                "FROM attempts a JOIN samples s ON s.id=a.sample_id "
                "LEFT JOIN deliveries d ON d.attempt_id=a.id "
                "LEFT JOIN attempt_observations post "
                "ON post.attempt_id=a.id AND post.phase='post' "
                "LEFT JOIN post_observation_checks check_row ON check_row.attempt_id=a.id "
                "WHERE a.id=?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise StateError("Unknown attempt")
            protocol = self.protocol(row["run_id"])
            self.require_protocol_serialization_stable(row["run_id"], protocol)
            if protocol.schema_version != "3.3":
                raise StateError("Post check recovery requires protocol 3.3")
            if row["finished_at"] is None or row["post_id"] is None:
                raise StateError("Delivered post observation is missing")
            if row["checked_id"] is not None:
                raise StateError("Post observation check already recorded")
            checked_at = now()
            gap = (
                datetime.fromisoformat(checked_at) - datetime.fromisoformat(row["finished_at"])
            ).total_seconds()
            self.db.execute(
                "INSERT INTO post_observation_checks VALUES (?,?,?)", (attempt_id, checked_at, gap)
            )
            self._event("post_observation_checked", attempt_id=attempt_id)
        return {
            "attempt_id": attempt_id,
            "run_id": row["run_id"],
            "checked_at": checked_at,
            "gap_seconds": gap,
            "status": self.attempt_observation_status(row["run_id"])["status"],
        }

    def attempt_observation_status(self, run_id: str) -> dict:
        protocol = self.protocol(run_id)
        if protocol.schema_version not in {"3.2", "3.3"}:
            return {"status": "not_required"}
        rows = self.db.execute(
            "SELECT a.id, a.started_at, d.finished_at, "
            "abort.recorded_at AS abort_at, abort.pre_age_seconds AS abort_age, "
            "post_check.checked_at AS post_check_at, "
            "pre.observation_id AS pre_id, pre_obs.recorded_at AS pre_at, "
            "post.observation_id AS post_id, post_obs.recorded_at AS post_at "
            "FROM attempts a JOIN samples s ON s.id=a.sample_id "
            "LEFT JOIN attempt_dispatch_aborts abort ON abort.attempt_id=a.id "
            "LEFT JOIN deliveries d ON d.attempt_id=a.id "
            "LEFT JOIN post_observation_checks post_check ON post_check.attempt_id=a.id "
            "LEFT JOIN attempt_observations pre ON pre.attempt_id=a.id AND pre.phase='pre' "
            "LEFT JOIN model_observations pre_obs ON pre_obs.id=pre.observation_id "
            "LEFT JOIN attempt_observations post ON post.attempt_id=a.id AND post.phase='post' "
            "LEFT JOIN model_observations post_obs ON post_obs.id=post.observation_id "
            "WHERE s.run_id=? ORDER BY a.started_at,a.id",
            (run_id,),
        ).fetchall()
        missing_pre = [row["id"] for row in rows if row["pre_id"] is None]
        missing_post = [row["id"] for row in rows if row["post_id"] is None]
        missing_post_check = [
            row["id"] for row in rows if row["post_id"] is not None and row["post_check_at"] is None
        ]
        violations = []
        gaps = []
        if protocol.schema_version == "3.3":
            timing = protocol.model_observation_timing
            assert timing is not None
            for row in rows:
                if row["abort_at"] is not None:
                    measurement = {
                        "attempt_id": row["id"],
                        "phase": "pre_dispatch",
                        "gap_seconds": row["abort_age"],
                        "limit_seconds": timing.max_pre_age_seconds,
                    }
                    gaps.append(measurement)
                    violations.append(measurement)
                for phase, start, end, limit in (
                    (
                        "pre",
                        row["pre_at"],
                        row["started_at"],
                        timing.max_pre_age_seconds,
                    ),
                    ("delivery", row["started_at"], row["finished_at"], None),
                    (
                        "post",
                        row["finished_at"],
                        row["post_at"],
                        timing.max_post_delay_seconds,
                    ),
                ):
                    if start is None or end is None:
                        continue
                    gap = (
                        datetime.fromisoformat(end) - datetime.fromisoformat(start)
                    ).total_seconds()
                    measurement = {
                        "attempt_id": row["id"],
                        "phase": phase,
                        "gap_seconds": gap,
                        "limit_seconds": limit,
                    }
                    gaps.append(measurement)
                    if gap < 0 or (limit is not None and gap > limit):
                        violations.append(measurement)
                if row["post_check_at"] is not None:
                    committed_gap = (
                        datetime.fromisoformat(row["post_check_at"])
                        - datetime.fromisoformat(row["finished_at"])
                    ).total_seconds()
                    measurement = {
                        "attempt_id": row["id"],
                        "phase": "post_commit",
                        "gap_seconds": committed_gap,
                        "limit_seconds": timing.max_post_delay_seconds,
                    }
                    gaps.append(measurement)
                    if committed_gap < 0 or committed_gap > timing.max_post_delay_seconds:
                        violations.append(measurement)
                    if row["post_at"] is not None:
                        confirmation_gap = (
                            datetime.fromisoformat(row["post_check_at"])
                            - datetime.fromisoformat(row["post_at"])
                        ).total_seconds()
                        confirmation = {
                            "attempt_id": row["id"],
                            "phase": "post_confirmation",
                            "gap_seconds": confirmation_gap,
                            "limit_seconds": None,
                        }
                        gaps.append(confirmation)
                        if confirmation_gap < 0:
                            violations.append(confirmation)
        return {
            "status": "timing_violation"
            if violations
            else "missing_pre"
            if missing_pre
            else "missing_post"
            if missing_post
            else "missing_post_check"
            if protocol.schema_version == "3.3" and missing_post_check
            else "complete",
            "attempts": len(rows),
            "missing_pre": missing_pre,
            "missing_post": missing_post,
            **(
                {
                    "missing_post_check": missing_post_check,
                    "timing_gaps": gaps,
                    "timing_violations": violations,
                }
                if protocol.schema_version == "3.3"
                else {}
            ),
        }

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
        if all(i["status"] == "unverified_development" for i in identities):
            if len({i["digest"] for i in identities}) != 1:
                return {
                    "status": "unresolved",
                    "reason": "declared identity changed",
                    "observations": len(records),
                }
            return {
                "status": "unverified_development",
                "observations": len(records),
                "digest": identities[0]["digest"],
                "reason": identities[0]["identity"]["reason"],
            }
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

    def protocol_manifest_digest(self, run_id: str) -> str:
        row = self.db.execute("SELECT manifest FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise StateError("Unknown run")
        return row["manifest"]

    def require_protocol_serialization_stable(self, run_id: str, protocol: Protocol) -> None:
        if protocol.digest != self.protocol_manifest_digest(run_id):
            raise StateError("Archived protocol serialization drift; use its original engine")

    def samples(self, run_id: str) -> list[dict]:
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM samples WHERE run_id=? ORDER BY task_key,replicate", (run_id,)
            )
        ]

    def begin_attempt(
        self,
        sample_id: str,
        request: PreparedRequest,
        *,
        pre_observation_id: int | None = None,
    ) -> str:
        """Commit dispatch intent before touching the network. Pending delivery stops resume."""
        with self.transaction():
            sample = self.db.execute("SELECT * FROM samples WHERE id=?", (sample_id,)).fetchone()
            if not sample:
                raise StateError("Unscheduled sample")
            protocol = self.protocol(sample["run_id"])
            self.require_protocol_serialization_stable(sample["run_id"], protocol)
            reject_model_credential(
                protocol.model, request.model_dump(mode="json"), "attempt request"
            )
            if self.model_identity(sample["run_id"])["status"] == "unresolved":
                raise StateError("Returned model identity requires adjudication")
            if self.discovery_status(sample["run_id"])["status"] == "unresolved":
                raise StateError("Model discovery requires adjudication")
            if protocol.schema_version in {"3.2", "3.3"}:
                if self.attempt_observation_status(sample["run_id"])["status"] != "complete":
                    raise StateError("Prior attempt lacks model observation evidence")
                if self.discovery_status(sample["run_id"])["status"] not in {
                    "stable_observed",
                    "unverified_development",
                }:
                    raise StateError("Protocol 3.2+ requires pre-dispatch model observation")
                row = self.db.execute(
                    "SELECT id,recorded_at FROM model_observations "
                    "WHERE run_id=? ORDER BY id DESC LIMIT 1",
                    (sample["run_id"],),
                ).fetchone()
                if pre_observation_id is None:
                    raise StateError("Protocol 3.2+ requires an explicit pre-observation ID")
                if row is None or pre_observation_id != row["id"]:
                    raise StateError("A newer observation intervened before dispatch")
            elif pre_observation_id is not None:
                raise StateError("Protocol 3.1 cannot bind a 3.2 pre-observation")
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
            started_at = now()
            if protocol.schema_version == "3.3":
                timing = protocol.model_observation_timing
                assert timing is not None
                pre_age = (
                    datetime.fromisoformat(started_at) - datetime.fromisoformat(row["recorded_at"])
                ).total_seconds()
                if pre_age < 0 or pre_age > timing.max_pre_age_seconds:
                    raise StateError("Protocol 3.3 pre-observation timing is outside frozen bounds")
            attempt_id = uuid.uuid4().hex
            request_id = self._blob(request.model_dump(mode="json"))
            self.db.execute(
                "INSERT INTO attempts VALUES (?,?,?,?,?)",
                (attempt_id, sample_id, ordinal, request_id, started_at),
            )
            if pre_observation_id is not None:
                self.db.execute(
                    "INSERT INTO attempt_observations VALUES (?,'pre',?)",
                    (attempt_id, pre_observation_id),
                )
            self._event(
                "attempt_started",
                attempt_id=attempt_id,
                sample_id=sample_id,
                request=request_id,
                **({"pre_observation_id": pre_observation_id} if pre_observation_id else {}),
            )
        if protocol.schema_version == "3.3":
            timing = protocol.model_observation_timing
            assert timing is not None
            checked_at = now()
            committed_age = (
                datetime.fromisoformat(checked_at) - datetime.fromisoformat(row["recorded_at"])
            ).total_seconds()
            if committed_age < 0 or committed_age > timing.max_pre_age_seconds:
                with self.transaction():
                    self.db.execute(
                        "INSERT INTO attempt_dispatch_aborts VALUES (?,?,?)",
                        (attempt_id, checked_at, committed_age),
                    )
                    self._event("attempt_dispatch_aborted", attempt_id=attempt_id)
                raise StateError("Protocol 3.3 pre-observation timing expired before dispatch")
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
        if self.db.execute(
            "SELECT 1 FROM attempt_dispatch_aborts b JOIN attempts a ON a.id=b.attempt_id "
            "WHERE a.sample_id=? AND a.ordinal=?",
            (sample_id, prior["ordinal"]),
        ).fetchone():
            return {"state": "timing_violation"}
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
    ) -> str | None:
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
            if self.db.execute(
                "SELECT 1 FROM attempt_dispatch_aborts WHERE attempt_id=?", (attempt_id,)
            ).fetchone():
                raise StateError("Aborted dispatch cannot be finished")
            run_id = self.db.execute(
                "SELECT run_id FROM samples WHERE id=?", (attempt["sample_id"],)
            ).fetchone()["run_id"]
            protocol = self.protocol(run_id)
            self.require_protocol_serialization_stable(run_id, protocol)
            request = PreparedRequest.model_validate_json(canonical(self.blob(attempt["request"])))
            try:
                request_evidence_binding(request, protocol.model, evidence)
            except (TypeError, ValueError) as exc:
                raise StateError("Delivery request evidence is invalid: " + str(exc)) from exc
            reject_model_credential(protocol.model, evidence, "delivery evidence")
            if generation is not None:
                reject_model_credential(
                    protocol.model, generation.model_dump(mode="json"), "generation"
                )
            received_at = now() if protocol.schema_version == "3.3" else None
            post_token = (
                secrets.token_urlsafe(32) if protocol.schema_version in {"3.2", "3.3"} else None
            )
            artifact = self._blob(evidence)
            self.db.execute(
                "INSERT INTO deliveries VALUES (?,?,?,?,?)",
                (attempt_id, kind, http_status, artifact, received_at or now()),
            )
            if post_token is not None:
                self.db.execute(
                    "INSERT INTO post_observation_claims VALUES (?,?)",
                    (attempt_id, hashlib.sha256(post_token.encode()).hexdigest()),
                )
            if generation is not None:
                content = self._blob(generation.model_dump(mode="json"))
                self.db.execute(
                    "INSERT INTO generations VALUES (?,?,?)",
                    (attempt["sample_id"], attempt_id, content),
                )
            self._event("attempt_finished", attempt_id=attempt_id, delivery=kind, evidence=artifact)
        return post_token

    def judge(self, sample_id: str, judge_digest: str, outcome: str, evidence: dict) -> None:
        if len(judge_digest) != 64 or any(c not in "0123456789abcdef" for c in judge_digest):
            raise StateError("Judge must have a content identity")
        with self.transaction():
            self._require_native_judge_claim(sample_id, judge_digest)
            self._require_model_observation_for_judgment(sample_id)
            row = self.db.execute("SELECT run_id FROM samples WHERE id=?", (sample_id,)).fetchone()
            protocol = self.protocol(row["run_id"])
            generation = self.db.execute(
                "SELECT content FROM generations WHERE sample_id=?", (sample_id,)
            ).fetchone()
            if generation is None:
                raise StateError("Judgment requires a returned generation")
            sample = self.db.execute(
                "SELECT task_key FROM samples WHERE id=?", (sample_id,)
            ).fetchone()
            try:
                campaign_judgment_binding(
                    protocol,
                    sample["task_key"],
                    generation["content"],
                    outcome,
                    evidence,
                    completion=Generation.model_validate_json(
                        canonical(self.blob(generation["content"]))
                    ).text,
                )
            except ValueError as exc:
                raise StateError(str(exc)) from exc
            reject_model_credential(
                protocol.model, {"outcome": outcome, "evidence": evidence}, "judgment"
            )
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
            self._require_native_judge_identity(sample_id, judge_digest)
            self._require_model_observation_for_judgment(sample_id)
            if self.db.execute(
                "SELECT 1 FROM judgments WHERE sample_id=? AND judge_digest=?",
                (sample_id, judge_digest),
            ).fetchone():
                raise StateError("Judgment already recorded")
            self.db.execute(
                "INSERT INTO judgment_claims VALUES (?,?,?)", (sample_id, judge_digest, now())
            )
            self._event("judgment_started", sample_id=sample_id, judge_digest=judge_digest)

    def _require_native_judge_identity(self, sample_id: str, judge_digest: str) -> bool:
        sample = self.db.execute("SELECT run_id FROM samples WHERE id=?", (sample_id,)).fetchone()
        if sample is None:
            raise StateError("Unscheduled sample")
        protocol = self.protocol(sample["run_id"])
        self.require_protocol_serialization_stable(sample["run_id"], protocol)
        if protocol.track in {"qhe-pinned-native-v1", "graybench-protected-semantic-v1"}:
            if judge_digest != protocol.judge_digest:
                label = "native" if protocol.track == "qhe-pinned-native-v1" else "protected"
                raise StateError(f"Frozen {label} judge identity mismatch")
            return True
        return False

    def _require_native_judge_claim(self, sample_id: str, judge_digest: str) -> None:
        if not self._require_native_judge_identity(sample_id, judge_digest):
            return
        if not self.db.execute(
            "SELECT 1 FROM judgment_claims WHERE sample_id=? AND judge_digest=?",
            (sample_id, judge_digest),
        ).fetchone():
            raise StateError("Track judgment requires a prior durable claim")

    def _require_model_observation_for_judgment(self, sample_id: str) -> None:
        sample = self.db.execute("SELECT run_id FROM samples WHERE id=?", (sample_id,)).fetchone()
        if sample is None:
            raise StateError("Unscheduled sample")
        run_id = sample["run_id"]
        if self.protocol(run_id).schema_version not in {"3.2", "3.3"}:
            return
        if self.attempt_observation_status(run_id)["status"] != "complete":
            raise StateError("Protocol 3.2+ judgment requires complete model observations")
        if self.discovery_status(run_id)["status"] not in {
            "stable_observed",
            "unverified_development",
        }:
            raise StateError("Protocol 3.2+ judgment requires stable model observation")

    def verify(self) -> dict:
        if self.db.in_transaction:
            return self._verify()
        self.db.execute("BEGIN")
        try:
            result = self._verify()
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _verify(self) -> dict:
        for row in self.db.execute("SELECT digest FROM blobs"):
            self.blob(row[0])
        previous, count = "0" * 64, 0
        events = []
        for row in self.db.execute("SELECT * FROM events ORDER BY seq"):
            count += 1
            expected = identity({"seq": count, "previous": previous, "payload": row["payload"]})
            if row["seq"] != count or row["previous"] != previous or row["digest"] != expected:
                raise StateError("Event chain is corrupt")
            previous = expected
            events.append(self.blob(row["payload"]))
        if self.db.execute("PRAGMA foreign_key_check").fetchone():
            raise StateError("Broken ledger relationship")
        try:
            bindings = verify_records(self.db, events)
        except (ValueError, KeyError, TypeError) as exc:
            raise StateError(str(exc)) from exc
        return {
            "events": count,
            "chain_head": previous,
            "integrity": "verified",
            "external_anchor": "not_checked",
            "row_bindings": bindings,
        }

    def summary(self, run_id: str) -> dict:
        # Multiple report queries must observe one SQLite snapshot during live dispatch.
        if self.db.in_transaction:
            return self._summary(run_id)
        self.db.execute("BEGIN")
        try:
            result = self._summary(run_id)
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _summary(self, run_id: str) -> dict:
        integrity = self.verify()
        protocol = self.protocol(run_id)
        recorded_protocol_digest = self.protocol_manifest_digest(run_id)
        rows = self.db.execute(
            "SELECT s.task_key,s.replicate,g.content,j.outcome,j.evidence FROM samples s "
            "LEFT JOIN generations g ON s.id=g.sample_id "
            "LEFT JOIN judgments j ON j.sample_id=s.id AND j.judge_digest=? WHERE s.run_id=? "
            "ORDER BY s.task_key,s.replicate",
            (protocol.judge_digest, run_id),
        ).fetchall()
        expected = {
            (key, repeat) for key in protocol.task_keys for repeat in range(protocol.repeats)
        }
        observed = {(row["task_key"], row["replicate"]) for row in rows}
        scored = {"pass", "fail", "candidate_error", "timeout"}
        outcomes = [r["outcome"] for r in rows]
        judgment_binding = {"bound": 0, "legacy_unbound": 0}
        for row in rows:
            if row["outcome"] is not None:
                status = campaign_judgment_binding(
                    protocol,
                    row["task_key"],
                    row["content"],
                    row["outcome"],
                    self.blob(row["evidence"]),
                    completion=Generation.model_validate_json(
                        canonical(self.blob(row["content"]))
                    ).text,
                )
                judgment_binding[status] += 1
        request_binding = {"bound": 0, "unbound": 0}
        for row in self.db.execute(
            "SELECT a.request,d.evidence FROM attempts a "
            "JOIN samples s ON s.id=a.sample_id "
            "JOIN deliveries d ON d.attempt_id=a.id WHERE s.run_id=?",
            (run_id,),
        ):
            status = request_evidence_binding(
                PreparedRequest.model_validate_json(canonical(self.blob(row["request"]))),
                protocol.model,
                self.blob(row["evidence"]),
            )
            request_binding[status] += 1
        counts = {
            name: outcomes.count(name)
            for name in (
                "pass",
                "fail",
                "candidate_error",
                "timeout",
                "unsupported",
                "infrastructure_error",
            )
        }
        counts["unjudged"] = outcomes.count(None)
        model_identity = self.model_identity(run_id)
        discovery = self.discovery_status(run_id)
        attempt_observations = self.attempt_observation_status(run_id)
        analysis_source = source_manifest()["digest"]
        blockers = []
        if recorded_protocol_digest != protocol.digest:
            blockers.append("protocol_serialization_drift")
        if analysis_source != protocol.analysis_digest:
            blockers.append("analysis_source_mismatch")
        if observed != expected or len(rows) != len(expected):
            blockers.append("frozen_cohort_mismatch")
        if any(r["content"] is None for r in rows):
            blockers.append("missing_generations")
        if counts["unjudged"]:
            blockers.append("unjudged_samples")
        for outcome in ("unsupported", "infrastructure_error"):
            if counts[outcome]:
                blockers.append(outcome)
        if model_identity["status"] == "unresolved":
            blockers.append("unresolved_returned_model_identity")
        if discovery["status"] == "unresolved":
            blockers.append("unresolved_model_discovery")
        if protocol.schema_version in {"3.2", "3.3"}:
            if discovery["status"] not in {"stable_observed", "unverified_development"}:
                blockers.append("model_discovery_not_observed")
            if attempt_observations["missing_pre"]:
                blockers.append("model_pre_observation_missing")
            if attempt_observations["missing_post"]:
                blockers.append("model_post_observation_missing")
            if protocol.schema_version == "3.3" and attempt_observations["missing_post_check"]:
                blockers.append("model_post_observation_check_missing")
            if protocol.schema_version == "3.3" and attempt_observations["timing_violations"]:
                blockers.append("model_observation_timing_violation")
        complete = not blockers and all(o in scored for o in outcomes)
        per_task = []
        for key in protocol.task_keys:
            task_rows = [r for r in rows if r["task_key"] == key]
            task_outcomes = [r["outcome"] for r in task_rows]
            per_task.append(
                {
                    "task_key": key,
                    "planned_samples": protocol.repeats,
                    "observed_samples": len(task_rows),
                    "passes": task_outcomes.count("pass"),
                    "outcomes": [
                        {"replicate": r["replicate"], "outcome": r["outcome"]} for r in task_rows
                    ],
                }
            )
        context_row = self.db.execute(
            "SELECT content FROM run_contexts WHERE run_id=?", (run_id,)
        ).fetchone()
        declared_setup = self.blob(context_row[0]).get("setup") if context_row else None
        recipe = declared_setup.get("evaluation_recipe") if type(declared_setup) is dict else None
        capability = protocol.model.capability_profile
        probe_status = _probe_artifact_status(protocol, declared_setup)
        return {
            "run_id": run_id,
            "protocol_digest": recorded_protocol_digest,
            "interpreted_protocol_digest": protocol.digest,
            "evaluation_recipe": recipe,
            "track": protocol.track,
            "extraction_policy": protocol.extraction,
            **(
                {
                    "suite": protocol.native_suite,
                    "population": protocol.native_population,
                    "native_cohort_digest": protocol.native_cohort_digest,
                    "native_exception_policy": protocol.native_exception_policy
                    or "conservative_unattributed_v1",
                    "denominator": len(expected),
                }
                if protocol.track == "qhe-pinned-native-v1"
                else {}
            ),
            **(
                {
                    "suite": protocol.protected_suite,
                    "population": protocol.protected_population,
                    "protected_cohort_digest": protocol.protected_cohort_digest,
                    "excluded": protocol.protected_excluded,
                    "denominator": len(expected),
                }
                if protocol.track == "graybench-protected-semantic-v1"
                else {}
            ),
            "planned_samples": len(expected),
            "observed_samples": len(rows),
            "returned_samples": sum(r["content"] is not None for r in rows),
            "judged_samples": sum(o is not None for o in outcomes),
            "complete": complete,
            "passes": outcomes.count("pass"),
            "pass_at_1": outcomes.count("pass") / len(expected) if complete else None,
            "score_status": "development_only" if complete else "unscored",
            "score_blockers": blockers,
            "outcome_counts": counts,
            "request_evidence_binding": request_binding,
            "judgment_evidence_policy": protocol.judgment_evidence_policy,
            "judgment_evidence_binding": judgment_binding,
            "cohort": {
                "missing": [list(slot) for slot in sorted(expected - observed)],
                "unexpected": [list(slot) for slot in sorted(observed - expected)],
            },
            "per_task": per_task,
            "estimator": "mean single-attempt success across frozen task/replicate slots",
            "certification": "not_certified",
            "publication_eligible": False,
            "publication_blockers": [
                "reviewed_task_and_protocol_admission_required",
                "independent_reproducibility_required",
                *(["provider_capability_profile_missing"] if capability is None else []),
                *(
                    ["provider_probe_artifacts_missing_or_invalid"]
                    if probe_status not in {"no_probe_claims", "verified_local_records"}
                    else []
                ),
                "provider_effective_settings_not_attested",
                *(["request_evidence_unbound"] if request_binding["unbound"] else []),
                *(["judgment_evidence_unbound"] if judgment_binding["legacy_unbound"] else []),
                *(
                    ["model_discovery_unverified"]
                    if discovery["status"] != "stable_observed"
                    else []
                ),
            ],
            "ledger_integrity": integrity,
            "analysis_identity": {
                "frozen": protocol.analysis_digest,
                "observed": analysis_source,
                "matched": analysis_source == protocol.analysis_digest,
            },
            "model_identity": model_identity,
            "model_discovery": discovery,
            "provider_capability": {
                "status": "operator_evidence_recorded" if capability else "missing",
                "profile_digest": capability.digest if capability else None,
                "profile": capability.model_dump(mode="json") if capability else None,
                "probe_digests": list(capability.probe_digests) if capability else [],
                "probe_artifacts_status": probe_status,
                "requested_settings": [
                    setting.model_dump(mode="json") for setting in protocol.model.settings
                ],
                "effective_settings_status": "not_attested",
            },
            "attempt_model_observations": attempt_observations,
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

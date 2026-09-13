"""
Database storage for benchmark results.

Provides SQLite-based persistent storage with support for:
- Run management
- Attempt recording
- Score aggregation
- Leaderboard generation
"""

import json
import platform
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from graybench.execution.outcomes import Outcome


def _json_serializer(obj):
    """JSON serializer for non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Outcome):
        return obj.value
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _as_text(value: Any) -> Optional[str]:
    """Coerce values to plain strings for SQLite storage."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


class Database:
    """
    SQLite-based storage for benchmark results.

    Schema:
    - runs: High-level run metadata
    - attempts: Individual task attempts
    - scores: Aggregated scores per run
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize storage.

        Args:
            db_path: Explicit database path, otherwise the configured workspace database.
        """
        if db_path is None:
            from graybench.config import get_global_config

            db_path = get_global_config().db_path
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript("""
                -- Runs table: one row per benchmark run
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    suite TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    n_samples INTEGER DEFAULT 1,
                    temperature REAL DEFAULT 0.0,
                    top_p REAL DEFAULT 1.0,
                    max_tokens INTEGER DEFAULT 4096,
                    timeout_seconds INTEGER DEFAULT 120,
                    dataset_version TEXT,
                    dataset_hash TEXT,
                    environment_info TEXT,
                    status TEXT DEFAULT 'running',
                    completed_at TEXT
                );
                
                -- Attempts table: one row per task attempt
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    sample_id INTEGER DEFAULT 0,
                    
                    -- Prompt and response
                    prompt TEXT NOT NULL,
                    completion TEXT,
                    
                    -- Code extraction
                    extracted_code TEXT,
                    extraction_success INTEGER,
                    
                    -- Execution results
                    outcome TEXT,
                    passed INTEGER,
                    error_type TEXT,
                    error_message TEXT,
                    stdout TEXT,
                    stderr TEXT,
                    
                    -- Performance metrics
                    generation_latency_ms REAL,
                    execution_time_ms REAL,
                    
                    -- Token usage
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    
                    -- Cost
                    cost_usd REAL,
                    
                    -- Raw API response (JSON)
                    raw_response TEXT,
                    
                    -- Timestamps
                    created_at TEXT NOT NULL,
                    
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                );
                
                -- Scores table: aggregated results per run
                CREATE TABLE IF NOT EXISTS scores (
                    run_id TEXT PRIMARY KEY,
                    total_tasks INTEGER,
                    passed INTEGER,
                    failed_test INTEGER,
                    failed_syntax INTEGER,
                    failed_import INTEGER,
                    failed_runtime INTEGER,
                    timeouts INTEGER,
                    extraction_failed INTEGER,
                    other_errors INTEGER,
                    pass_rate REAL,
                    
                    -- Aggregate metrics
                    total_input_tokens INTEGER,
                    total_output_tokens INTEGER,
                    total_cost_usd REAL,
                    avg_generation_latency_ms REAL,
                    avg_execution_time_ms REAL,
                    
                    FOREIGN KEY (run_id) REFERENCES runs (run_id)
                );
                
                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_attempts_run ON attempts (run_id);
                CREATE INDEX IF NOT EXISTS idx_attempts_task ON attempts (task_id);
                CREATE INDEX IF NOT EXISTS idx_attempts_outcome ON attempts (outcome);
                CREATE INDEX IF NOT EXISTS idx_runs_provider ON runs (provider, model);
                CREATE INDEX IF NOT EXISTS idx_runs_suite ON runs (suite);
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_run(
        self,
        suite: str,
        provider: str,
        model: str,
        n_samples: int = 1,
        temperature: float = 0.0,
        top_p: float = 1.0,
        max_tokens: int = 4096,
        timeout_seconds: int = 120,
        dataset_version: str = None,
        dataset_hash: str = None,
        manifest: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new benchmark run.

        Returns:
            run_id: Unique identifier for this run
        """
        run_id = str(uuid.uuid4())[:8]
        created_at = datetime.now(timezone.utc).isoformat()

        # Collect environment info
        env_info = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "manifest": manifest or {},
            "packages": __import__("graybench.preflight", fromlist=["environment"]).environment()[
                "packages"
            ],
        }

        # Try to get Qiskit version
        try:
            import qiskit

            env_info["qiskit_version"] = qiskit.__version__
        except ImportError:
            pass

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, created_at, suite, provider, model,
                    n_samples, temperature, top_p, max_tokens, timeout_seconds,
                    dataset_version, dataset_hash, environment_info, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    created_at,
                    suite,
                    provider,
                    model,
                    n_samples,
                    temperature,
                    top_p,
                    max_tokens,
                    timeout_seconds,
                    dataset_version,
                    dataset_hash,
                    json.dumps(env_info),
                    "running",
                ),
            )

        return run_id

    def record_attempt(
        self,
        run_id: str,
        task_id: str,
        prompt: str,
        completion: str,
        extracted_code: str,
        extraction_success: bool,
        outcome: str,
        passed: bool,
        error_type: Optional[str],
        error_message: Optional[str],
        stdout: str,
        stderr: str,
        generation_latency_ms: float,
        execution_time_ms: float,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        raw_response: Dict[str, Any],
        sample_id: int = 0,
    ):
        """Record a single task attempt."""
        prompt = _as_text(prompt) or ""
        completion = _as_text(completion) or ""
        extracted_code = _as_text(extracted_code) or ""
        outcome = _as_text(outcome) or ""
        error_type = _as_text(error_type)
        error_message = _as_text(error_message)
        stdout = _as_text(stdout) or ""
        stderr = _as_text(stderr) or ""
        created_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO attempts (
                    run_id, task_id, sample_id, prompt, completion,
                    extracted_code, extraction_success,
                    outcome, passed, error_type, error_message, stdout, stderr,
                    generation_latency_ms, execution_time_ms,
                    input_tokens, output_tokens, total_tokens, cost_usd,
                    raw_response, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    task_id,
                    sample_id,
                    prompt,
                    completion,
                    extracted_code,
                    int(extraction_success),
                    outcome,
                    int(passed),
                    error_type,
                    error_message,
                    stdout,
                    stderr,
                    generation_latency_ms,
                    execution_time_ms,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cost_usd,
                    json.dumps(raw_response, default=_json_serializer),
                    created_at,
                ),
            )

    def complete_run(self, run_id: str):
        """Mark a run as completed and calculate scores."""
        completed_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                raise ValueError("Unknown run")
            manifest = json.loads(run["environment_info"]).get("manifest", {})
            planned = manifest.get("task_ids")
            actual = [
                r[0]
                for r in conn.execute("SELECT task_id FROM attempts WHERE run_id = ?", (run_id,))
            ]
            if not actual or len(actual) != len(set(actual)):
                raise ValueError("Cannot complete an empty run or a run with duplicate attempts")
            if planned is not None and sorted(actual) != sorted(planned):
                raise ValueError("Incomplete run: recorded attempts do not match planned task IDs")
            if conn.execute(
                "SELECT COUNT(*) FROM attempts WHERE run_id = ? AND outcome = 'api_error'",
                (run_id,),
            ).fetchone()[0]:
                raise ValueError(
                    "Operational API failures prevent a valid completed benchmark; retain the run for diagnosis"
                )
            # Update run status
            conn.execute(
                """
                UPDATE runs SET status = 'completed', completed_at = ?
                WHERE run_id = ?
            """,
                (completed_at, run_id),
            )

            # Calculate scores
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
                    SUM(CASE WHEN outcome = 'fail_test' OR outcome = 'fail_assertion' THEN 1 ELSE 0 END) as failed_test,
                    SUM(CASE WHEN outcome = 'fail_syntax' OR outcome = 'fail_indentation' THEN 1 ELSE 0 END) as failed_syntax,
                    SUM(CASE WHEN outcome = 'fail_import' OR outcome = 'fail_module_not_found' THEN 1 ELSE 0 END) as failed_import,
                    SUM(CASE WHEN outcome LIKE 'fail_%%' AND outcome NOT IN ('fail_test', 'fail_assertion', 'fail_syntax', 'fail_indentation', 'fail_import', 'fail_module_not_found') THEN 1 ELSE 0 END) as failed_runtime,
                    SUM(CASE WHEN outcome = 'timeout' THEN 1 ELSE 0 END) as timeouts,
                    SUM(CASE WHEN outcome = 'extraction_failed' OR outcome = 'no_function_found' THEN 1 ELSE 0 END) as extraction_failed,
                    SUM(CASE WHEN outcome IN ('error_other', 'api_error', 'empty_completion') THEN 1 ELSE 0 END) as other_errors,
                    SUM(input_tokens) as total_input,
                    SUM(output_tokens) as total_output,
                    CASE WHEN COUNT(cost_usd) = COUNT(*) THEN SUM(cost_usd) ELSE NULL END as total_cost,
                    AVG(generation_latency_ms) as avg_gen_latency,
                    AVG(execution_time_ms) as avg_exec_time
                FROM attempts
                WHERE run_id = ?
            """,
                (run_id,),
            )

            row = cursor.fetchone()

            pass_rate = row["passed"] / row["total"] if row["total"] > 0 else 0.0

            conn.execute(
                """
                INSERT OR REPLACE INTO scores (
                    run_id, total_tasks, passed,
                    failed_test, failed_syntax, failed_import, failed_runtime,
                    timeouts, extraction_failed, other_errors,
                    pass_rate,
                    total_input_tokens, total_output_tokens, total_cost_usd,
                    avg_generation_latency_ms, avg_execution_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_id,
                    row["total"],
                    row["passed"],
                    row["failed_test"],
                    row["failed_syntax"],
                    row["failed_import"],
                    row["failed_runtime"],
                    row["timeouts"],
                    row["extraction_failed"],
                    row["other_errors"],
                    pass_rate,
                    row["total_input"],
                    row["total_output"],
                    row["total_cost"],
                    row["avg_gen_latency"],
                    row["avg_exec_time"],
                ),
            )

    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get run metadata."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_scores(self, run_id: str) -> Optional[Dict]:
        """Get scores for a run."""
        run = self.get_run(run_id)
        if run is None or run["status"] != "completed":
            return None
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM scores WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            scores = dict(row)
            if scores["total_tasks"]:
                from graybench.metrics import wilson_interval

                low, high = wilson_interval(scores["passed"], scores["total_tasks"])
                scores.update(wilson_95_low=low, wilson_95_high=high)
            return scores

    def get_attempts(self, run_id: str) -> List[Dict]:
        """Get all attempts for a run."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM attempts WHERE run_id = ? ORDER BY task_id, sample_id", (run_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_runs(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        suite: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """List runs with optional filtering."""
        query = "SELECT * FROM runs WHERE 1=1"
        params = []

        if provider:
            query += " AND provider = ?"
            params.append(provider)
        if model:
            query += " AND model = ?"
            params.append(model)
        if suite:
            query += " AND suite = ?"
            params.append(suite)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_leaderboard(self, suite: str = "normal") -> List[Dict]:
        """Comparable cohorts only; historical/unvalidated runs remain in results list."""
        from graybench.preflight import fingerprint

        entries = []
        for run in self.list_runs(suite=suite, limit=10000):
            if run["status"] != "completed":
                continue
            info = json.loads(run["environment_info"])
            manifest = info.get("manifest", {})
            if manifest.get("protocol") != "graybench-v2" or not manifest.get("preflight"):
                continue
            scores = self.get_scores(run["run_id"])
            if not scores:
                continue
            cohort = {
                k: run[k]
                for k in (
                    "suite",
                    "dataset_hash",
                    "temperature",
                    "top_p",
                    "max_tokens",
                    "timeout_seconds",
                )
            }
            cohort["manifest"] = {
                k: v
                for k, v in manifest.items()
                if k not in {"preflight", "budget_usd", "estimated_token_cap_cost_usd", "workers"}
            }
            cohort["environment"] = {k: v for k, v in info.items() if k != "manifest"}
            entries.append(
                {
                    **run,
                    **scores,
                    "cohort": fingerprint(cohort)[:12],
                    "coverage": len(manifest["task_ids"]) / manifest["dataset_size"],
                    "track": manifest["track"],
                }
            )
        return sorted(entries, key=lambda e: (e["cohort"], -e["pass_rate"], e["created_at"]))

    def delete_run(self, run_id: str):
        """Delete a run and all associated data."""
        with self._connect() as conn:
            conn.execute("DELETE FROM attempts WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM scores WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))


# Alias for backwards compatibility
ResultStorage = Database

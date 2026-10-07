# Terminal abandonment of incomplete runs

An uncertain delivery or interrupted judgment must not be erased or retried to
obtain a better answer. `abandonment-plan` and `abandon-run` supply the terminal
path required by the [recovery audit](attempt-recovery-state-audit.md), without
turning uncertainty into a failed candidate or repairing a score.

Stop all workers for the run before planning abandonment. The required
`--workers-stopped` flag records an operator declaration; the engine does not
inspect process ownership, stop workers or prove the declaration. This is not
a live cancellation mechanism. A worker still running after abandonment will
be refused when it tries to append execution evidence. Obtain and preserve any
available response/verdict evidence before choosing terminal abandonment.

```text
graybench abandonment-plan LEDGER RUN_ID PLAN --reason "Interrupted run; evidence preserved" --workers-stopped
graybench abandon-run LEDGER PLAN
graybench summary LEDGER RUN_ID
```

Planning opens an existing ledger read-only and verifies a single snapshot.
The exclusive plan retains the run, raw serialized protocol-manifest identity,
analysis source, full summary, ledger chain/count, reason and stopped-worker
declaration. Reasons must contain non-whitespace text, be at most 4,096
characters and pass the existing loaded-credential checks. Duplicate JSON keys
are refused. No provider discovery, generation, judging or Docker occurs.
SQLite can manage WAL/shared-memory sidecars even for a read-only connection.

Commit acquires the ledger's immediate write transaction and exactly recomputes
the snapshot before appending a typed immutable record and its bound event.
Any intervening append, including to another run in the same ledger, invalidates
the plan. Replan from the changed state rather than editing a stale snapshot.
Two concurrent commits cannot both close a run. Neither command silently creates
a missing ledger or overwrites an existing plan.

Already complete runs cannot be abandoned. A fully scored archived cohort whose
only current blocker is a changed analysis source also cannot be abandoned;
source drift does not invalidate the historical completed measurement. Other
incomplete states retain every scheduled slot, original attempt, observation,
delivery, generation and judgment claim/result. No original row is replaced,
deleted, relabeled or converted into an outcome. The record preserves the exact
pre-closure unscored summary as well as the reason for closure.

Abandonment is irreversible within this append-only ledger. Further attempts,
delivery commits, observations, post-observation timing recovery, judgment claims
and judgments are rejected inside their transactions. Generation, judgment,
upstream, native and protected schedulers stop before transport or oracle work;
direct discovery also refuses before touching its transport. Abandoned summaries
retain the original denominator and diagnostics, add `run_abandoned`, and have
`complete: false`, `pass_at_1: null` and `publication_eligible: false`.
Repeated-sample and comparison paths consequently withhold cohort scores.

Verification binds the terminal row, typed record, plan digest, run/protocol
identities and preceding ledger chain/count. It checks retained cohort counts
and rejects execution events following closure. Event ownership follows the
bound kind, so unrelated identifier fields cannot redirect the closed-run check.
These are local relational and chronological consistency checks. They do not
replay every historical summary claim under an unavailable old engine, attest
the author's identity, externally anchor the ledger, prove workers stopped or
prevent selective study reporting. A database owner can remove enforcement and
rewrite evidence; a correctly rehashed file alone is not external authentication.

Historical read-only databases without the optional abandonment table remain
readable. Creating that empty table on a writable reopen does not change the
integrity-report table list or invalidate a frozen plan by itself. Existing
protocol serialization and unclosed summary schemas are preserved. Historical
evidence files and existing provider ledgers are not modified by this addition.

[Verification evidence](artifacts/run-abandonment-2026-10-07/README.md) includes
actual worker exits without cleanup at six durable boundaries, followed by
reopening the same ledger, committing terminal closure and reopening read-only.
The tests use fixed authored answers and synthetic metadata, not model calls.
This workflow closes an incomplete run operationally; it does not provide
provider-side retrieval, restore a lost observation token, rerun an interrupted
oracle, resume the abandoned run or qualify a benchmark release.

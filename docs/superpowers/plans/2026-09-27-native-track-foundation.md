# Native Track Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a frozen, suite-specific native Qiskit HumanEval evaluation path whose judgments retain exact task and runtime identities without making premature publication claims.

**Architecture:** A new native cohort contract binds one pinned suite, task records, exclusions, extraction, runtime image and execution limits before any generation. A separate worker executes the assembled answer and original pinned test in one isolated Python interpreter, while a host supervisor controls Docker and records the result. New release-bound judgment identities enter the immutable ledger without reinterpreting historical V3 records; reporting remains development-only until a separately verified publication gate exists.

**Tech Stack:** Python 3.12, Pydantic 2, SQLite, Docker, pinned Qiskit 2.4.2 image, pytest.

**Spec:** `docs/superpowers/specs/2026-09-27-dual-track-qhe-design.md`

## Global Constraints

- New track ID: `qhe-pinned-native-v1`; existing `upstream` and revision recipe IDs keep their meanings.
- Normal and hard have distinct suite IDs, task lists and scores; neither is pooled into a headline percentage.
- The 143-task offline subset excludes pinned external-service IDs 43, 97, 98, 122, 129, 133, 134 and 146; it cannot be labeled a 151-task result.
- The candidate and pinned test execute in one Python 3.12/Qiskit 2.4.2 process inside an immutable image with no network, credentials, host user files or Docker socket.
- Native execution preserves pinned Python/Qiskit semantics but cannot guarantee that a malicious same-process candidate cannot inspect or alter tests.
- All new scores remain development-only until task admission, independent review, external anchoring and clean-machine reproduction are complete.
- Historical V2/V3 ledgers and judgments remain readable under their original identities.

## Review Focus

- A mixed normal/hard cohort must be rejected before generation; Task 1 tests this.
- A task file that invokes `check` twice or unexpectedly must be rejected rather than rewritten; Task 2 tests this.
- A candidate that exits early or prints a forged success marker must never receive a passing judgment; Tasks 2 and 3 test this.
- A task or image changed after freezing must stop the evaluation; Tasks 1 and 4 test this.
- A complete development run must not be presented as publication eligible or pooled across suites; Task 4 tests this.

---

### Task 1: Frozen native cohort

**Files:**
- Create: `engine/src/graybench/native_cohort.py`
- Create: `engine/tests/test_native_cohort.py`

**Interfaces:**
- Consumes: `JudgeTask`, `PINS`, `EXTERNAL_IDS`, `ExtractionPolicy`, `source_manifest`, `Contract`.
- Produces: immutable `NativeCohort` with `track`, `suite`, `population`, `label`, `task_keys`, `task_digests`, `excluded`, `dataset_pin`, `image`, `extraction`, `source_digest`, and a constant-false `publication_eligible` property. `freeze_native_cohort(tasks: tuple[JudgeTask, ...], *, cache: Path, suite: Literal["normal", "hard"], population: Literal["offline_143", "custom_development"], image: str, extraction: ExtractionPolicy, label: str, excluded: dict[str, str]) -> NativeCohort`; `validate_native_cohort(cohort: NativeCohort, tasks: tuple[JudgeTask, ...], *, cache: Path) -> None`. Both functions re-read the exact SHA-256-pinned parquet through `load_suite`; caller-supplied task records alone cannot establish pinned provenance.

- [x] **Step 1: Write failing tests** for a 143-task offline cohort, exact per-task digest binding, distinct normal/hard identities, rejection of mixed suites, duplicated IDs, changed task bytes, wrong exclusion map, and a custom development cohort. Assert `track == "qhe-pinned-native-v1"`, `publication_eligible is False`, and the expected 143/151 labels cannot be interchanged. Scan all 151 pinned test ASTs per suite to verify the expected top-level `check` call shape before relying on Task 2's assembly rule.
- [x] **Step 2: Run** `engine/.venv/Scripts/python.exe -m pytest engine/tests/test_native_cohort.py -q`; expect missing import or assertions failing for the new contract.
- [x] **Step 3: Implement** the two named functions and immutable `NativeCohort` in `native_cohort.py`. Bind the pinned revision and parquet SHA-256, exact ordered task keys and digests, image digest, extraction policy, source digest, declared exclusions, and population. Require offline exactly the pinned 143 IDs. Keep custom cohorts explicitly `development_only`.
- [x] **Step 4: Run** the focused tests and `engine/.venv/Scripts/python.exe -m ruff check engine/src/graybench/native_cohort.py engine/tests/test_native_cohort.py`; expect both pass.
- [x] **Step 5: Commit** the contract and tests.

### Task 2: Exact native test assembly and worker

**Files:**
- Create: `engine/src/graybench/native_assembly.py`
- Create: `engine/src/graybench/native_worker.py`
- Create: `engine/tests/test_native_worker.py`

**Interfaces:**
- Consumes: `JudgeTask`, `extract(completion, task.public, policy)` and one `NativeCohort` task binding from Task 1.
- Produces: `check_test_shape(task) -> None` and `native_payload(task, completion, extraction) -> dict` in the host-side assembly module; a standard-library-only worker entry point that writes a bounded structured result only after the pinned test returns. The worker file can be copied into the pinned image without installing the host engine or its credentials.

- [x] **Step 1: Write failing tests** for original normal public-prefix assembly, one hard top-level `check` call, reference pass, incorrect answer fail, a task with two check calls rejected, candidate `os._exit(0)` nonpass, candidate stdout forgery nonpass, and preserved input mutation/aliasing in one interpreter.
- [x] **Step 2: Run** `engine/.venv/Scripts/python.exe -m pytest engine/tests/test_native_worker.py -q`; expect the new interfaces to be absent or the new cases to fail.
- [x] **Step 3: Implement** AST shape validation in `native_assembly.py` and the standard-library-only worker in `native_worker.py`. Execute the extracted answer and original test bytes in one namespace; append exactly one trusted `check` invocation only for normal tests with no top-level call. Distinguish assertion failure, candidate exception, worker infrastructure failure and missing completion evidence. Keep candidate stdout separate from the trusted result file and bound serialized evidence.
- [x] **Step 4: Run** focused tests and Ruff; expect both pass.
- [x] **Step 5: Commit** the worker and tests.

### Task 3: Isolated native Docker supervisor

**Files:**
- Create: `engine/src/graybench/native_judge.py`
- Create: `engine/tests/test_native_judge.py`

**Interfaces:**
- Consumes: `NativeCohort`, `native_payload`, the pinned image digest and `Judgment`.
- Produces: `NativeJudge.evaluate(task, completion) -> Judgment` and a manifest with per-task digest, extraction, worker hash, image, limits, and track ID.

- [x] **Step 1: Write failing tests** for exact Docker flags, read-only filesystem and bounded tmpfs, no network, no mounted host user files or socket, timeout, memory/process/CPU cap, output cap, missing completion evidence, forged stdout, and a pinned normal/hard reference and negative control.
- [x] **Step 2: Run** `engine/.venv/Scripts/python.exe -m pytest engine/tests/test_native_judge.py -q`; expect failure before implementation.
- [x] **Step 3: Implement** the supervisor, separating a candidate/test container from host evidence collection. Require an immutable image digest; never treat process exit zero or stdout text alone as a pass. Use a fresh empty host temporary directory mounted only at `/result` for the completion file because Docker discards `/tmp` tmpfs on exit; keep the worker source on a distinct read-only mount, validate the stopped-container result as one bounded regular file, and delete the temporary directory. Record image and worker identities and return `infrastructure_error` for supervisor failures.
- [x] **Step 4: Run** focused tests in the pinned image and Ruff; expect both pass.
- [x] **Step 5: Commit** the supervisor and tests.

### Task 4: Ledger-bound native judgments and separate development reports

**Files:**
- Modify: `engine/src/graybench/contracts.py`
- Modify: `engine/src/graybench/ledger.py`
- Modify: `engine/src/graybench/ledger_evidence.py`
- Create: `engine/src/graybench/native_campaign.py`
- Create: `engine/tests/test_native_campaign.py`
- Modify: `engine/src/graybench/cli.py`

**Interfaces:**
- Consumes: Tasks 1–3, existing generation `Protocol`, `Ledger`, `Judgment`.
- Produces: a versioned native protocol/campaign binding and a report with one suite, explicit denominator, per-task outcomes, and `publication_eligible: false`.

- [x] **Step 1: Write failing tests** proving a frozen native task set cannot switch suite, task bytes, extraction, image, judge, or source on resume; an interrupted native judgment does not silently rerun; old V3 protocol digests and ledgers remain unchanged; mixed-suite or mixed-track reporting is rejected; a complete native development run remains ineligible for publication.
- [x] **Step 2: Run** `engine/.venv/Scripts/python.exe -m pytest engine/tests/test_native_campaign.py -q`; expect failure before implementation.
- [x] **Step 3: Implement** an additive versioned binding and CLI commands for freezing and stepping a native campaign, retaining old schema semantics. Use the existing append-only claim/event path for the new judgment identity. Report the explicit suite and population without a combined headline score.
- [x] **Step 4: Run** the focused tests, the complete engine suite, Ruff, and a pinned-image reference/control replay; expect all to pass, with any unsupported tasks reported explicitly.
- [ ] **Step 5: Commit** the integration and verification evidence, then update the draft PR description around the final behavior.

## Follow-on plans

The protected value-contract track, adapter code attestation and typed capability checks, response extraction repair, task-card admission, external anchoring, public release gate, model campaigns, and independent reproduction remain required. They receive separately reviewable plans and cannot be inferred complete from this native increment.

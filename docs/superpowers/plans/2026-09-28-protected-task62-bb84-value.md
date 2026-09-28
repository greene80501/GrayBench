# Protected Task-62 BB84 Value Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a separately named protected, value-based BB84 sender revision for pinned task 62 that rejects the observed fixed-input false pass while preserving all native evidence.

**Architecture:** A source-bound task constructor freezes the revised public prompt and a bounded predeclared case set. The existing value runner executes candidate functions in isolation; a host-side oracle independently derives BB84 amplitudes, validates the returned vector and records the verdict. The protected registry and authored-control runner opt the task in without changing historical task-2/20 identities.

**Tech Stack:** Python 3.12, Pydantic contracts, pytest, locked `uv`, pinned Qiskit Docker image.

**Spec:** [Protected task-62 BB84 sender value revision](../specs/2026-09-28-protected-task62-bb84-value.md)

## Global Constraints

- Preserve byte-identical pinned normal and hard source tasks and prior evidence.
- Keep native and protected tracks separately named; never present a protected value result as native Qiskit-object equivalence.
- Freeze exact source ancestry, public contract, private cases, oracle code and runtime identity before a candidate runs.
- Keep `release_eligible` and publication eligibility false pending independent review and full release gates.
- Do not enable GitHub Actions while account billing blocks jobs; validate locally.

## Review Focus

- A fixed five-qubit completion must fail on other declared inputs despite passing the upstream pinned test.
- A correct alternative with a global phase must pass, while a relative X-basis sign error must fail.
- Reversing Qiskit's qubit order must fail on asymmetric inputs; all-zero cases alone are inadequate.
- Non-finite, malformed, bool-as-int and wrong-length output must not bypass value validation.
- Normal completion and hard standalone prompts must convey the same semantic contract without leaking cases.

---

### Task 1: Source-bound public contract and cases

**Files:**
- Create: `engine/src/graybench/protected_task62.py`
- Modify: `engine/src/graybench/protected_semantic_judge.py`
- Modify: `engine/src/graybench/protected_task_registry.py`
- Test: `engine/tests/test_protected_task62.py`

**Interfaces:**
- Consumes: `JudgeTask`, `ProtectedValueContract`, `ValueCall`, `ValueShape`, `ProtectedSemanticTask`.
- Produces: `task62_value_task(source: JudgeTask) -> ProtectedSemanticTask`, `TASK62_ORACLE`.

- [x] **Step 1: Write failing tests** for exact source digests, the two prompt formats, binary-list domain, distinct frozen cases and registry reconstruction.
- [x] **Step 2: Run** `uv run --locked pytest -q tests/test_protected_task62.py` and verify these tests fail for the missing revision.
- [x] **Step 3: Implement** the constructor and oracle identity. Exhaust widths 1–3, then add fixed mixed cases for widths 4–5; keep the case count within 256.
- [x] **Step 4: Run** the focused tests and verify they pass.

### Task 2: Independent host-side judgment

**Files:**
- Modify: `engine/src/graybench/protected_semantic_judge.py`
- Test: `engine/tests/test_protected_task62.py`

**Interfaces:**
- Consumes: one case's binary state/basis and one candidate JSON amplitude vector.
- Produces: `_task62_bb84_value(state: object, basis: object, value: object) -> dict` and a source-bound `ProtectedSemanticJudge.manifest`/`evaluate` path.

- [x] **Step 1: Write failing tests** for Z/X basis states, little-endian indexing, global phase, fixed answer, ignored argument, reversed bit order and invalid values.
- [x] **Step 2: Run** the focused tests and observe the expected failure.
- [x] **Step 3: Implement** direct product-factor expectations, strict shape checks, norm and phase-aligned tolerance; include task-62 constructor code hash in the manifest.
- [x] **Step 4: Run** focused tests and relevant existing protected-semantic tests.

### Task 3: Predeclared authored controls and campaign selection

**Files:**
- Modify: `engine/src/graybench/protected_oracle_review.py`
- Modify: `engine/src/graybench/cli.py`
- Test: `engine/tests/test_protected_task62.py`

**Interfaces:**
- Consumes: the exact task-62 revision and pinned runtime image.
- Produces: task-62 `Probe` controls and `protected-oracle-review --task 62`; existing task-2/20 defaults remain unchanged.

- [x] **Step 1: Write failing tests** for positive and negative control identities, task selection and historical default behavior.
- [x] **Step 2: Run** focused tests to confirm the new behavior is absent.
- [x] **Step 3: Add** analytic, Qiskit and phase positives plus fixed, input-ignoring, order and sign mutants; expand explicit task selection and keep old defaults.
- [x] **Step 4: Run** focused tests, then predeclared normal/hard controls under the pinned Docker image.

### Task 4: Evidence, documentation and verification

**Files:**
- Create: `docs/reliability-evidence/protected-task62-bb84-value.md`
- Modify: `engine/README.md`
- Add a byte-pinned local control bundle only after the exact source and tests are stable.

**Interfaces:**
- Consumes: source-bound control log, pinned dataset cache and judge manifests.
- Produces: an inspectable development evidence record; no model score.

- [x] **Step 1: Verify** the source-bound control log and expected outcomes; investigate any mismatch before preserving it.
- [x] **Step 2: Document** contract differences from pinned native task 62, cases, limits, results and remaining admission blockers.
- [x] **Step 3: Run** Ruff, focused tests, full pinned-image suite and evidence verification locally.
- [x] **Step 4: Request** read-only code review, fix findings, commit and push under `greene80501`, then update draft PR #3 without enabling Actions.

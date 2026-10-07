# BB84 Explicit Bases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit, deterministic, protected development recipe for task 63 in both normal and hard formats without altering upstream results.

**Architecture:** A focused BB84 revision module owns prompt revision, fixed semantic check and corrected reference. The existing recipe and campaign machinery freezes that revision before generation, then delegates protected execution to graph protocol 4. Separate evidence replays positive and negative controls and verifies normal/hard source identity.

**Tech Stack:** Python 3.12, Qiskit 2.4.2 in immutable Docker image, pytest, existing GrayBench graph protocol 4 and ledger.

**Spec:** `docs/superpowers/specs/2026-09-27-bb84-explicit-bases.md`

## Global Constraints

- Preserve pinned upstream task bytes and historical judgments.
- Apply one identical revised contract to all models before request freezing; no examples or private fixture values in provider requests.
- Candidate and judge remain separated; use graph protocol 4 without fallback.
- Keep `release_eligible: false`; no model API calls in development verification.

## Review Focus

- A normal body-only answer must receive the revised three-argument function prefix; a full definition must retain only public imports.
- Hard prompt/revision must use the same argument order and semantic contract.
- Same basis inputs with different circuit bits must produce different keys, rejecting basis-only answers.
- No matching bases must produce the empty string; bit order must follow ascending qubit index.
- Saved campaign setup and comparison must reconstruct the revised prompt/check and reject original-record substitution.

---

### Task 1: Frozen public revision and identity

**Files:** Create `engine/src/graybench/bb84_revision.py`; modify `engine/src/graybench/evaluation_recipes.py`; test `engine/tests/test_bb84_revision.py` and `engine/tests/test_evaluation_recipes.py`.

**Interfaces:** `BB84Judge.revise(task: JudgeTask) -> JudgeTask`, `.configuration(task)`, `.evaluate(task, completion)`; recipe name `qhe63-explicit-bases-v1`.

- [x] Write tests for normal/hard signature and contract, wrong-family rejection, idempotent revision, frozen request digest, old-task substitution rejection, and protocol-3 rejection.
- [x] Run tests red for missing recipe/revision (four expected failures).
- [x] Implement revision, corrected reference and manifest with pinned-source and revised digests and protocol 4; retain separate upstream track.
- [x] Run focused offline tests green, lint and format.
- [ ] Commit the revision together with its checker and evidence after final review.

### Task 2: Protected semantic check and controls

**Files:** Modify `engine/src/graybench/bb84_revision.py`; test `engine/tests/test_bb84_revision.py`.

**Interfaces:** `BB84_CHECK` fixed trusted test source; corrected reference in `BB84Judge.revise()`.

- [x] Write Docker-enabled tests for both task formats and replay the exact pinned variants. Include corrected reference, independent statevector alternative, fixed-string/basis-only/no-sifting/reversed-order controls, equivalent circuit preparation and error separation.
- [x] Run the fixed-one control red against an in-memory weakened single-case checker, then green against the real protected checker.
- [x] Implement the fixed trusted case table and independent classical expected-key calculation; every case gets a fresh circuit.
- [x] Run protected controls green on the immutable Python 3.12 image; run relevant campaign/graph regressions, lint and format.
- [ ] Commit the oracle and controls with the revision after final review.

### Task 3: Immutable calibration evidence and documentation

**Files:** Add raw/verified artifacts and a method note under `docs/reliability-evidence/`; update `docs/reliability-evidence/evaluation-recipes.md`, `docs/ORACLE_REVIEW_FINDINGS.md` and the draft PR body.

**Interfaces:** Existing source-guarded evidence runner and append-only verifier.

- [x] Declare reference and adversarial cases before execution, with original task/public digests and expected outcomes.
- [x] Run protected normal/hard evidence without model API calls; verify complete chains, case identities, source manifest, image and raw hashes.
- [x] Document exact passes/failures/unsupported outcomes, limits, ineligible status and how to select the new recipe.
- [ ] Run required checks, secret scan, commit as Wyatt Greene, push and update draft PR; confirm CI.

Execution ruling: tasks 1 and 2 will be committed together with task 3, because
the prompt, corrected reference and checker form one usable recipe. The cost is
less commit-level bisection within this increment; source-bound raw evidence,
red/green test output and task-specific files retain the review boundaries.

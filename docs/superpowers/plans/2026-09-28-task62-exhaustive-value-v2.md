# Task-62 Exhaustive Protected Value v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exhaustive, separately versioned protected task-62 value condition that rejects the demonstrated v1 false pass while preserving historical evidence.

**Architecture:** Extend the existing semantic-task validator to admit exactly the 1,364 ordered task-62 inputs under a new oracle identity. Keep v1 explicit and make v2 the default development revision after controls pass. Use the existing isolated value runner and host BB84 oracle; add one v2-only input-specific control and freeze source-bound evidence.

**Tech Stack:** Python 3.12, Pydantic, pytest, Ruff, pinned QHE parquet cache, pinned Docker image.

**Spec:** [Task-62 exhaustive protected value v2](../specs/2026-09-28-task62-exhaustive-value-v2.md)

## Global Constraints

- Preserve the exact v1 constructor, 124 ordered calls, explicit selection, and historical logs.
- V2's public value contract is byte-identical to v1's; normal and hard source task digests remain pinned.
- The full domain contains 1,364 calls, ordered by width, state, then basis.
- The protected value condition remains development-only and makes no native-circuit or model-score claim.
- Do not query billable providers or enable GitHub Actions for this work.

## Review Focus

- A missing, duplicated, reordered, or malformed v2 case must fail construction.
- The old v1 oracle must still reconstruct all 124 cases after v2 becomes default.
- The width-4 input-specific mutant must fail v2 in both suites, while correct analytic, Qiskit-derived, and global-phase variants pass.
- A resource failure must retain its execution outcome and never be converted to semantic `fail`.
- The frozen admission bundle must remain independently verifiable after the current source and registry advance.

---

### Task 1: Freeze the v2 identity and finite case set

**Files:** Modify `engine/src/graybench/protected_semantic_judge.py`, `engine/src/graybench/protected_task62.py`, `engine/tests/test_protected_task62.py`, `engine/tests/test_protected_semantic_judge.py`.

**Interfaces:** Add `TASK62_ORACLE_V2`, `task62_case_pairs_v2()`, and `task62_value_task_v2(source: JudgeTask) -> ProtectedSemanticTask`; keep the v1 names and behavior.

- [x] Write tests for exactly 1,364 distinct ordered calls, the omitted v1 input, v1 reconstruction, and rejection of missing/reordered/changed cases.
- [x] Run the focused tests and confirm they fail for the absent v2 behavior.
- [x] Implement the v2 constructor and exact-case validator; increase the schema maximum only to 1,364.
- [x] Run focused tests and Ruff; confirm no v1 regression.
- [ ] Commit the tested identity and validation change.

### Task 2: Make the isolated judge and registry select v2 safely

**Files:** Modify `engine/src/graybench/protected_semantic_judge.py`, `engine/src/graybench/protected_task_registry.py`, `engine/tests/test_protected_campaign.py`, `engine/tests/test_protected_task62.py`.

**Interfaces:** `revised_value_task(source, oracle=None)` defaults task 62 to v2 and selects v1 or v2 explicitly; `ProtectedSemanticJudge.manifest/evaluate` use the task-62 code and BB84 oracle for either identity.

- [x] Write tests for distinct v1/v2 digests, exact old-oracle replay, v2 default selection, and outcome propagation for execution failure.
- [x] Run focused tests red.
- [x] Add registry and dispatch branches, preserving source ancestry and no release eligibility.
- [x] Run focused tests green, Ruff, and commit.

### Task 3: Add the omitted-input mutant and run both-suite controls

**Files:** Modify `engine/src/graybench/protected_oracle_review.py`, `engine/tests/test_protected_task62.py`; create a new byte-pinned `docs/reliability-evidence/artifacts/task62-protected-exhaustive-2026-09-28/` bundle and update `docs/reliability-evidence/protected-task62-bb84-value.md`.

**Interfaces:** `protected_probes(source, *, oracle=None)` preserves eight v1 controls and includes a ninth v2-only wrong candidate. `run_protected_review` binds probes to the predeclared revision.

- [x] Test that v1 keeps eight controls, v2 adds the exact wrong-input control, and the review runner predeclares the selected judge.
- [x] Run focused tests red, implement the selector, run green.
- [x] Execute 18 controls under the pinned image and verify three positive and six negative outcomes per suite, including the omitted-input mutant.
- [x] Save the immutable log, byte hashes, source and runtime manifests, and a local verifier; run it and commit.

### Task 4: Carry the admission inventory forward without rewriting history

**Files:** Create a new successor under `docs/reliability-evidence/artifacts/`, create a deterministic builder in `docs/reliability-evidence/`, update `docs/reliability-evidence/admission-control-audit.md`, and add focused admission tests if builder behavior needs coverage.

**Interfaces:** `refresh_finding_registry(old_inventory, cache)` preserves card review work and adds the current task-62 finding; `verify_admission_bundle(bundle, cache)` replays exact saved bytes.

- [x] Verify the predecessor bundle and assert its old finding registry fails the current-registry gate while historical validation still passes.
- [x] Build a successor from the pinned predecessor, preserve its first three logs byte-for-byte, replace the task-62 log, refresh source and finding registry, then recompute the audit.
- [x] Verify the successor from exact bytes and independently reproduce it in a second directory; keep publication eligibility false and no finding auto-resolution.
- [x] Run the full applicable local suite, Ruff, review the diff, commit, push to draft PR #3, and update its description.

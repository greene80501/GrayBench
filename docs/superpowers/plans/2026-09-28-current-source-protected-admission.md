# Current-Source Protected Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve a verified admission successor in which all 42 bound protected controls share its inventory engine source.

**Architecture:** Reuse the existing source-bound oracle logs and schema-5 bundle verifier. A deterministic docs-side builder checks the predecessor, binds six cards to the newly declared judges, and saves a new immutable successor without mutating historical bundles.

**Tech Stack:** Python 3.12, pinned QHE parquet cache, Docker-pinned Qiskit runtime, canonical JSON/JSONL.

**Spec:** `docs/superpowers/specs/2026-09-28-current-source-protected-admission.md`

## Global Constraints

- Never replace prior bundles or logs.
- Keep `publication_eligible` false and no model-score claim.
- Freeze the image and current engine-source digest stated in the spec.

## Review Focus

- A changed predecessor or new control log must stop the successor build.
- A judge manifest whose canonical identity differs from the predeclared header must stop the build.
- A changed candidate case, requirement link, or omitted-input result must stop the build.
- The saved audit must replay byte-for-byte, with exactly 42 inventory-source bound controls.
- Rebuilding from unchanged inputs must reproduce every pinned file byte-for-byte.

---

### Task 1: Reconfirm source-bound controls

**Files:** Preserve two new protected JSONL logs in the successor bundle.

**Interfaces:** `run_protected_review(cache, output, suite="both", image=IMAGE, task_ids=...)`; `inspect_oracle_review(output, cache)`.

- [x] Run task-2/20 and task-62 exhaustive-v2 controls under the pinned image and one source.
- [x] Verify 24/24 and 18/18 expected outcomes, six predeclared judge manifests and the exact task-62 omitted-input miss in each suite.

### Task 2: Build and replay the successor

**Files:** Create `docs/reliability-evidence/refresh_admission_current_controls.py`, `docs/reliability-evidence/artifacts/admission-current-controls-2026-09-28/`, and update `.gitattributes` and admission documentation.

**Interfaces:** `build(cache: Path, task2_20_log: Path, task62_log: Path, output: Path) -> dict`.

- [x] Verify predecessor, current logs, source identities, exact case metadata, judge manifests, requirement links, and the omitted-input failure before writing.
- [x] Advance the inventory source and changed protected judge digests; retain two upstream logs and all other cards byte-for-byte.
- [x] Recompute and verify the schema-5 audit with 60 controls, 42 inventory-source bound controls, zero different-source bound controls and publication false.
- [x] Rebuild to a second output and compare every pinned file byte-for-byte.
- [x] Run focused checks, Ruff, the appropriate local regression suite and diff review; commit and push as Wyatt Greene to draft PR #3.

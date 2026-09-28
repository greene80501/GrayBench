# Dual-track Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let native and protected campaigns use the frozen paired-family comparison CLI without losing their distinct cohort and task ancestry.

**Architecture:** Preserve `ComparisonPlan` and bootstrap math. Add track-aware task binding in `comparison.py` and setup dispatch/validation in `cli.py`, reusing each setup's existing cohort validator. Report statuses and publication blockers stay unchanged.

**Tech Stack:** Python 3.12, Pydantic contracts, pinned QHE cache, SQLite ledger, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-28-dual-track-comparison-design.md`.

## Global Constraints

- Keep native and protected results separate; never pool normal and hard.
- Preserve historical comparison JSON identity and existing bootstrap method.
- Never infer provider setting equivalence from a free-text operator note.
- Do not create a new score or set `publication_eligible` true.
- Do not enable GitHub Actions; verify locally with the pinned Python 3.12/Qiskit image.

## Review Focus

- Protected source versus revised task digests must both bind the dataset identity.
- Native extraction and exception policy mismatches must be rejected before a plan exists.
- Stored run context must match the plan and pinned cohort before reporting.
- A plan must reject wrong or mixed tracks, suite, denominator, population, and exclusions.
- Historical comparison bytes retain their recorded raw digest; parsing may
  add later ModelSpec defaults, so never silently reissue an old score.

## Task 1: Track-aware plan binding

**Files:** Modify `engine/src/graybench/comparison.py`; extend `engine/tests/test_comparison.py`.

- [x] Write failing tests for native and protected task binding, protected wrong ancestry, and mixed-track/mismatched-condition rejection. Verify the raw historical artifact digest without relabeling a parsed model.
- [x] Run red tests, implement one track-aware binding function and keep the statistical method unchanged.
- [x] Run focused tests, Ruff and format; commit.

## Task 2: Setup-aware CLI

**Files:** Modify `engine/src/graybench/cli.py`, add focused native/protected CLI tests to `engine/tests/test_comparison.py`, update `engine/README.md`.

- [x] Write failing CLI tests for plan and report on both new tracks, wrong setup kind, altered stored context, and exclusive output.
- [x] Run red tests; dispatch by frozen track and call each setup's existing pinned-cohort validator. Reuse `compare_runs` for read-only ledger summaries.
- [x] Run focused tests, Ruff and format; commit.

## Task 3: Assurance and integration

**Files:** Create `docs/reliability-evidence/dual-track-comparison.md` and update this plan.

- [ ] Document exact metric and release limitations, including model-setting non-equivalence and unscorable cases.
- [ ] Run the complete pinned Python 3.12/Qiskit Docker-enabled engine suite, `git diff --check`, and independent read-only review; fix Important findings and rerun if source changes.
- [ ] Push to draft PR #3 under `greene80501`, update its body with the exact local result, and verify both Actions workflows remain disabled.

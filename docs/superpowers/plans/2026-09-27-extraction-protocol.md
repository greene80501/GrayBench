# Versioned Extraction Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separately frozen, test-independent code-block selector for development comparisons without changing historical extraction behavior.

**Architecture:** `extract` dispatches by immutable policy name. Planning binds that name through `Protocol`, CLI, and concrete judges; judge manifests and cohort validation reject mismatches. All raw responses and outcomes stay in the append-only ledger.

**Tech Stack:** Python 3.12, Pydantic, pytest, pinned Docker judge image.

**Spec:** `docs/superpowers/specs/2026-09-27-extraction-protocol-design.md`

## Global Constraints

- Keep `raw_or_single_python_fence_v1` behavior unchanged.
- Add `unique_entrypoint_fence_v2` only as a separately named development condition; no retrospective pilot rescoring.
- Selection may use response structure and public `entry_point`, never tests, canonical solutions, or model identity.
- Do not add imports, code repair, multiple candidate attempts, or an unscored fallback.
- Freeze both extraction policy and actual judge identity before any generation.

## Review Focus

- A valid function block followed by an example call and ASCII diagram selects only the unique function block.
- Two plausible function blocks or two definitions in one block reject rather than choosing one.
- Malformed or nested fences reject rather than accidentally capturing executable text.
- A missing hard-suite import remains missing after selection.
- A forged protocol extraction label cannot run a different judge policy.

---

### Task 1: Policy parser and adverse controls

**Files:** Modify `engine/src/graybench/extraction.py`; test `engine/tests/test_extraction.py`.

**Interfaces:** `extract(text: str, task: PublicTask, policy: ExtractionPolicy = "raw_or_single_python_fence_v1") -> Extracted`; export `ExtractionPolicy`, `EXTRACTION_POLICIES`.

- [x] Add focused tests for the five review cases, raw/single-fence equivalence, labels, and surrounding prose; confirm new tests fail.
- [x] Implement v2 with complete-fence accounting, Python AST top-level definition counting, and deterministic ambiguity errors. Preserve v1 path.
- [x] Run focused extraction tests and Ruff; check exact pilot answer structure through a read-only external probe without changing its ledger.

### Task 2: Bind planning and judgment to policy

**Files:** Modify `engine/src/graybench/contracts.py`, `campaign_setup.py`, `cli.py`, `upstream.py`, `file_judge.py`, `evaluation_campaign.py`; test `engine/tests/test_campaign_plan.py`, `test_evaluation_recipes.py`, `test_extraction.py` and relevant campaign tests.

**Interfaces:** `Protocol.extraction: ExtractionPolicy`; `build_setup(..., extraction: ExtractionPolicy = v1)`; `recipe_judge(..., extraction=...)`; CLI `campaign-plan --extraction`; concrete judges retain `.extraction` and bind the name in manifests.

- [x] Add failing setup/CLI round-trip, judge-digest-difference, and forged-policy pre-dispatch tests.
- [x] Thread the policy through setup and concrete judges; validate actual policy against frozen protocol before dispatch.
- [x] Record extraction method/reason in protected judgment evidence, run focused tests and Ruff.

### Task 3: Verification and evidence

**Files:** Update `engine/README.md`, `docs/reliability-evidence/openai-compatible-development.md`, and a new extraction-policy evidence document.

- [x] Run representative positive and negative candidates in pinned Docker for both normal and hard, and probe the exact preserved pilot format read-only without rejudging the pilot ledger.
- [x] Run the complete Docker-enabled Python 3.12 suite; inspect JUnit, failed/error/skip counts, and source/image identities.
- [ ] Check credential patterns, staged diff, frozen artifact hashes, and independent review findings; commit under greene80501, push draft PR #3, update PR description, and verify all GitHub checks.

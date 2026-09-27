# Task 82 Header Adjudication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned task 82 recipe that scores definitively non-QPY output as wrong while preserving v1 and leaving ambiguous parser failures unscored.

**Architecture:** `QpyFileJudge` selects v1 or v2 explicitly; only v2 examines the fixed QPY magic after artifact capture and before isolated parsing. Campaign setup and CLI freeze the selected recipe as they do other revisions.

**Tech Stack:** Python 3.12, Docker, Qiskit, pytest.

**Spec:** `docs/reliability-evidence/task82-header-adjudication-design.md`

## Global Constraints

- Historical `task82-file-semantic-v1` outcomes and public prompt stay unchanged.
- No candidate-selected verdict, host QPY deserialization, or implicit recipe fallback.
- The QPY prefix is exactly the six bytes `QISKIT` per IBM's format specification.
- All task 82 recipes remain development-only.

## Review Focus

- V1 malformed output must remain unscored.
- V2 empty/wrong/truncated prefix must fail after artifact capture.
- V2 valid prefix plus parser error must remain unscored.
- Normal/hard reference and equivalent valid circuits must pass in v2.
- Campaign setup/CLI must preserve the v2 recipe and reject wrong-family tasks.

---

### Task 1: Versioned header rule

**Files:** Modify `engine/src/graybench/file_judge.py`, `engine/src/graybench/evaluation_recipes.py`; test `engine/tests/test_file_judge.py`, `engine/tests/test_evaluation_recipes.py`.

**Interfaces:** `QpyFileJudge(..., track="task82-file-semantic-v1")` permits v1/v2; `recipe_judge("task82-file-semantic-v2", ...)` constructs v2.

- [x] Write failing tests for v2 header cases and retained v1 outcome; observe red.
- [x] Implement v2-only fixed-prefix rule and manifest identity.
- [x] Run focused protected tests and exact normal/hard reference replay.
- [x] Run complete Docker regression, lint and diff checks.
- [ ] Review, commit under Wyatt Greene, push to draft PR #3 and verify CI.

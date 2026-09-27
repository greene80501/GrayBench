# Task 82 Patched Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse task 82's untrusted QPY under a separately pinned Qiskit 2.5.2 image while preserving the historical candidate and oracle runtimes.

**Architecture:** Extend the existing three-container semantic track with an explicit parser image digest, frozen in the judgment manifest. Build a parser-only derivative of the historical image from a hash-pinned Qiskit wheel. Keep the track release-ineligible.

**Tech Stack:** Python 3.12, Qiskit QPY, Docker, pytest.

**Spec:** `docs/reliability-evidence/task82-patched-parser-design.md`

## Global Constraints

- The historical candidate/oracle image is `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
- The parser wheel is Qiskit 2.5.2 Linux x86-64 CPython abi3, SHA-256 `28fcb983e565b8f027a13ef43cda7aaeb1f1a6caf9df07408708abcf7bc0b59d` from PyPI.
- No release admission or model-score claim follows from this change.

## Review Focus

- A mutable or malformed parser image must fail before candidate execution.
- The manifest must distinguish old-parser and patched-parser judgments.
- Candidate and oracle must never switch images with the parser.
- Valid QPY from the old runtime must parse on the patched runtime.
- Malformed files and parser limits must remain unscored, not false fails.

---

### Task 1: Freeze a separate parser runtime

**Files:** Modify `engine/src/graybench/file_judge.py`, `engine/src/graybench/qpy_decoder.py`; test `engine/tests/test_file_judge.py`.

**Interfaces:** `QpyFileJudge(..., parser_image: str | None = None)`; `decode_qpy(data, *, image, ...)` uses the selected parser image.

- [ ] Write tests for digest validation, manifest identity, and parser-only image routing.
- [ ] Run focused tests and observe the expected failure.
- [ ] Implement the smallest routing and evidence change.
- [ ] Run focused tests, lint, and format checks.

### Task 2: Build and verify the parser image

**Files:** Create `engine/parser/Dockerfile`, `engine/parser/requirements.lock`; update `docs/reliability-evidence/task82-semantic-track.md`.

**Interfaces:** Immutable local Docker image digest with Qiskit 2.5.2, other packages inherited from the historical image.

- [ ] Bind `FROM` to the full historical digest as well as a local tag, then build with the SHA-256-pinned Qiskit wheel; verify a deliberately retargeted tag cannot change the inherited layers.
- [ ] Inspect image digest and verify Python/Qiskit versions in a disposable container.
- [ ] Run protected task 82 controls with the original candidate/oracle image and new parser image.
- [ ] Preserve command, digest, outcomes and remaining limitations in the evidence document.
- [ ] Run appropriate regression and diff checks, review, commit as Wyatt Greene, push to draft PR #3, and check CI.

### Task 3: Freeze patched parsing through campaign planning

**Files:** Modify `engine/src/graybench/campaign_setup.py`, `engine/src/graybench/evaluation_recipes.py`, `engine/src/graybench/cli.py`; test `engine/tests/test_evaluation_recipes.py`.

**Interfaces:** `build_setup(..., parser_image: str | None = None)` and `campaign-plan --parser-image sha256:...` only for `task82-file-semantic-v1`; `CampaignSetup.parser_image` reconstructs the same judge.

- [ ] Write failing tests for frozen setup/reconstruction, mutation rejection, CLI planning and wrong-recipe rejection.
- [ ] Run focused tests and observe the expected failure.
- [ ] Implement minimal setup/recipe/CLI routing.
- [ ] Run focused tests, then rerun complete Docker regression if sources changed after its first run.

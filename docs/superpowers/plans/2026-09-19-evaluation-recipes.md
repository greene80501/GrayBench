# Explicit Evaluation Recipes Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan inline under the existing approved overhaul authorization.

**Goal:** Run existing explicit revisions through frozen campaign planning, generation, protected judgment and reporting.

**Architecture:** A fixed recipe registry delegates to existing judges and applies the task 141 public revision before planning. CampaignSetup stores the recipe; cohort checks, summaries and comparison reconstruct its identities.

**Tech Stack:** Python 3.12, Pydantic, SQLite, existing Docker isolation and provider adapters.

**Spec:** `docs/superpowers/specs/2026-09-19-evaluation-recipes.md`

## Global constraints

- Preserve original upstream tasks and historical evidence.
- Do not send private tests/reference solutions to providers.
- No recipe fallback, silent task omission, answer repair or certification claim.
- No model generation calls needed for this integration's validation.

## Review focus

- Wrong-family selection must fail before any provider call.
- A task 141 answer must be bound to the revised public request.
- Saved setup reconstruction must reproduce all task/judge/request digests.
- File-parser and output limits must be bound rather than ignored.
- Comparison must use revised tasks, while context-free upstream comparisons remain supported.

## Task 1: Recipe selection and frozen planning

Files: create `engine/src/graybench/evaluation_recipes.py`; modify
`campaign_setup.py`, `evaluation_campaign.py`, `file_judge.py`; create
`engine/tests/test_evaluation_recipes.py`.

Interfaces: `recipe_judge(recipe, **kwargs)` returns an object exposing `image`,
`track`, `configuration(task)`, `evaluate(task, answer)`, and `revise(task)` for
revised recipes. `build_setup(..., evaluation_recipe="upstream")` freezes the
selected recipe and revised cohort. `CampaignSetup.tasks(cache)` reloads and
validates the same revised records.

- [x] Add and run a failing offline planning test:
  ```python
  setup = build_setup("revision", model, (task141,), image,
                      evaluation_recipe="qhe141-pauli-group-anticommutator-v1")
  assert setup.protocol.track == "strengthened"
  assert setup.protocol.request_digests[key] != original_request.digest
  ```
- [x] Implement the fixed recipes `upstream`, `qhe0-size-domain-v1`,
  `task82-file-semantic-v1`, and `qhe141-pauli-group-anticommutator-v1`.
  Dispatch to UpstreamJudge, CircuitSizeJudge, QpyFileJudge and
  PauliAnticommutatorJudge respectively; apply `.revise` only for task 141.
  Reject unknown recipe names and wrong task families explicitly.
- [x] Add round-trip reconstruction, wrong-family and limits-binding assertions;
  run `pytest tests/test_evaluation_recipes.py tests/test_campaign_plan.py`.

## Task 2: CLI, reporting and lifecycle verification

Files: modify `engine/src/graybench/cli.py`, `ledger.py`; extend
`engine/tests/test_evaluation_recipes.py` and `engine/README.md`.

Interfaces: `campaign-plan --evaluation-recipe NAME` persists the selection;
`campaign-step` uses that setup; summaries expose the declared recipe when a
setup exists. For strengthened comparisons, retrieve and validate the saved
CampaignSetup from each ledger before calling `compare_runs` with revised tasks.

- [x] Add failing CLI planning and protected lifecycle tests with mocked HTTP:
  ```python
  assert campaign.step()["state"] == "dispatched"
  assert campaign.step()["outcome"] == "pass"
  assert ledger.summary(run)["evaluation_recipe"] == recipe
  ```
  Inspect the actual captured request for the revised contract and absence of
  private sentinels. Reject original/unrevised task records before dispatch.
- [x] Implement CLI selection and comparison reconstruction; retain raw pinned
  task loading for context-free upstream comparison fixtures.
- [x] Run focused tests, then the full Docker-enabled suite and Ruff checks.
  Execute a source-bound local lifecycle demonstration with deterministic HTTP
  and real protected judgment; retain its ledger and report separately from scores.
- [x] Document commands, development-only status and original-source replay rules;
  scan for credentials, commit under the user identity, and update PR 3.

## Execution record

Baseline: 4a534fc. Both implementation tasks completed; the fresh-context reviewer
found one important parser output-limit propagation defect. The real Docker
regression failed at the expected boundary before the fix, then passed. Final
suite: 365 passed in 136.20 seconds; Ruff checks pass. Six fixture runs completed
twelve protected judgments against pinned normal/hard tasks; all expected outcomes
matched and ledger verification passed. These are not model scores.

Ruling: retain the historical UpstreamCampaign class name for compatibility while
validating the selected judge track; renaming is unnecessary for recipe integrity.
Ruling: bind recipe selection in CampaignSetup and judge manifests rather than
duplicating it in Protocol; reconstruction validates all existing identities.
Ruling: preserve source-specific earlier evidence and require original bytes for
replay; newly enabled recipes cannot retroactively change prior public contracts.

Review scope was this plan's changes against 4a534fc. It does not certify the
entire rewrite or the scientific validity of existing oracles. No deferred minor
findings were reported. Overall benchmark admission and calibration remain open.

# Trusted Judge Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve the trusted upstream judge's exact final message and verify task-110 controls against their authored plan rather than only their own metadata.

**Architecture:** Capture the bounded UTF-8 stdout line plus its parsed JSON, size, and digest. Declare the capture policy in the judge manifest. The oracle-review inspector verifies captured outcomes for manifests declaring that policy. A task-110-specific verifier reconstructs exact source tasks, prompts, tests, controls, extraction, manifests, and transcript identities. Existing log bytes remain historical evidence, with their exact development revision archived.

**Tech Stack:** Python 3.12, existing Docker graph/proxy judges, pytest, content identities.

**Spec:** The task-110 design requires exact case identities, judge manifests, candidate hashes, worker outcomes, and the log chain to reproduce. Current inspection omits exact authored-case reconstruction and does not retain the final trusted message. A hash chain proves local consistency only; it cannot authenticate its author or certify a model score.

## Global Constraints

- Preserve old evidence bytes and identify historical engine sources honestly.
- Capture only complete, bounded, finite JSON judgments with unique keys and the declared outcome schema.
- Host errors without a final trusted judgment must remain visibly uncaptured.
- Keep native and protected track semantics separate and release-ineligible pending the broader review.

## Review Focus

- Rehashed outcome or worker-evidence edits must conflict with the captured message.
- Duplicate JSON keys, nonfinite values, and incomplete messages must be rejected.
- An altered completion, dropped case, or different declared judge must conflict with the authored task-110 plan.
- Proxy and graph protocols must both capture real trusted messages.
- Historical logs without the new policy must remain inspectable without a current-source claim.

### Task 1: Final trusted message capture

**Files:** Create `engine/src/graybench/upstream_evidence.py` and `engine/tests/test_upstream_evidence.py`; modify `engine/src/graybench/upstream.py` and `engine/src/graybench/oracle_review.py`.

- [x] Write failing pure capture/verification tests and real proxy/graph integration tests.
- [x] Implement `capture_judgment(raw, limit)` and `verify_judgment(outcome, evidence)`; declare and save the capture in `UpstreamJudge`.
- [x] Verify declared captured messages in oracle-review inspection; preserve old-log behavior.
- [ ] Run pure and Docker tests, plus relevant existing bridge and oracle-review tests. Offline checks pass; live integration checks await a healthy Docker daemon.

### Task 2: Exact task-110 control verification

**Files:** Archive the old task-110 revision; extend the current development module and its tests; create a fresh dated control log and README.

- [x] Write failing tests for rehashed completion, case, manifest, transcript, and outcome changes.
- [x] Reconstruct exact authored cases and source bindings in a dedicated verifier.
- [ ] Generate new Docker control evidence only after Docker is healthy, and verify it from a fresh clone.
- [x] Update the PR with current-source and historical evidence scopes; commit under greene80501 with `[skip ci]`.

Ruling: Existing user authorization covers implementation and pushing the same PR. No additional approval gate is needed for these changes. Docker startup currently fails on the previously rejected socket-removal action; offline work continues while the user's cleanup request is pending.

## Review and verification ledger

The independent code review found four missing checks: dropped captures on trusted errors, dropped wrapped evidence, nested graph session/sequence/protocol changes, and non-object trusted stdout. Each received a failing regression before its fix. The follow-up review found no remaining correctness blockers and reproduced 49 passing focused tests with 10 skipped live/cache-dependent cases. Current-log fixtures synthesize terminal captures solely for verifier unit tests; they are not observed Docker evidence. The archived October 6 revision and log retain their exact bytes and historical source identities. Local hashes and captured bytes establish consistency, not author authenticity or oracle quality.

Final offline full-suite verification: 1,277 passed, 377 skipped, 12 Windows temporary-directory cleanup warnings, zero failures in 141.07 seconds. Neither the Docker image nor the dataset-cache test environment variable was enabled for that run. Ruff lint and formatting checks passed using the engine configuration. The [October 7 release audit](../../reliability-evidence/artifacts/current-release-audit-2026-10-07/README.md) preserves all 1,510 prepared public prompts and explicitly reports the prior inventory's source mismatch. Docker-dependent tests and fresh observed task-110 controls remain pending.

A fresh clone of `8e380fd` installed the locked Python 3.12 dependencies and reproduced 49 focused passing tests with 10 skipped cases, the exact audit report hash, and the archived development-module hash. Ruff lint and formatting also passed from that clone's `engine/` directory with the engine configuration. PR #3 now identifies the new source digest and distinguishes current offline verification from historical Docker evidence. Both implementation and this ledger use the user's Git identity and `[skip ci]`.

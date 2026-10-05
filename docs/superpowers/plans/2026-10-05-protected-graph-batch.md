# Protected Graph Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned benchmark-owned graph batch so task 63 can test its authored valid-input matrix without treating transport timeouts as wrong answers.

**Architecture:** The trusted process constructs one graph of positional cases and requests an opt-in batch. The host relays it unchanged; the candidate worker loops over the candidate's ordinary entry point and returns result values. A separate task-63 v2 recipe declares its test, limits, and condition identity; v1 remains available.

**Tech Stack:** Python 3.12, pytest, Qiskit/Aer in immutable Docker image, protocol-4 graph transport.

**Spec:** [Protected graph batch design](../specs/2026-10-05-protected-graph-batch-design.md)

## Global Constraints

- Keep candidate source free of private test code, expected values, and benchmark-supplied model wrappers.
- Preserve default protocol-4 single-call envelopes and the existing task-63 v1 recipe.
- Batch mode is explicit in the judge manifest and task payload; at most 1024 nonempty positional cases.
- Malformed transport and resource limits cannot become a wrong-answer verdict.
- Task-63 v2 remains development-only until admission and independent review.

## Review Focus

- A candidate function inspects caller frames: expected answers remain solely in the trusted process.
- A candidate mutates inputs or retains state: document and test that batch is a distinct condition from repeated calls.
- A candidate raises on a later case: stop at that case and preserve candidate-error classification.
- An oversized or malformed batch: reject before invoking any candidate function.
- A wrong result at a late index: ensure the trusted judge examines every returned value and fails.

---

### Task 1: Opt-in protected graph batch transport

**Files:** Modify `engine/src/graybench/upstream.py`, `engine/src/graybench/upstream_graph_process.py`, `engine/src/graybench/sandbox.py`, `engine/src/graybench/graph_worker.py`; test `engine/tests/test_graph_bridge.py`.

**Interfaces:** `UpstreamJudge(..., graph_batch="positional-batch-v1")` enables `candidate.batch(cases)` only in trusted tests. The request carries a batch marker; `Candidate.call_graph(..., batch=True)` relays it; the worker executes the existing entry point for each positional tuple and returns a tuple. Default is no batch.

- [ ] Write Docker-backed tests for a correct multi-case batch, undeclared batch rejection, malformed case rejection before candidate execution, later-case exception, and late wrong answer.
- [ ] Run the focused tests with `GRAYBENCH_TEST_IMAGE` set to the pinned digest and verify they fail because batch support is missing.
- [ ] Implement manifest-bound opt-in, envelope validation, worker loop, and trusted proxy method with no candidate-supplied wrapper.
- [ ] Run focused tests, existing graph bridge tests, and Ruff; review that old single-call manifest fields and envelopes remain unchanged.
- [ ] Commit the transport and its tests.

### Task 2: Separate task-63 v2 recipe

**Files:** Create `engine/src/graybench/bb84_batch_revision.py`; modify `engine/src/graybench/evaluation_recipes.py`; test `engine/tests/test_bb84_batch_revision.py`.

**Interfaces:** `BB84BatchJudge.revise`, `.configuration`, and `.evaluate` parallel the v1 judge but select the batch mode and a frozen 588-case trusted test. `recipe_judge("qhe63-explicit-bases-v2", ...)` selects it.

- [ ] Write tests for unchanged public prompt/signature, exact case count and expected-key construction, distinct manifest identity, old recipe preservation, two correct controls and wrong/exception controls on both suites.
- [ ] Run focused tests and verify failure from missing v2 recipe.
- [ ] Implement the new revision and recipe, with 584 exhaustive widths 1–3 plus four explicit v1 stress cases; keep `release_eligible: false`.
- [ ] Run focused Docker controls, recipe/setup tests, and Ruff.
- [ ] Commit the recipe and tests.

### Task 3: Freeze evidence and assess admission

**Files:** Add a source-bound artifact under `docs/reliability-evidence/artifacts/`, update `docs/reliability-evidence/task63-explicit-bases-revision.md`, and amend PR #3.

**Interfaces:** Raw control log plus manifest/verifier report exact test, source, image, judge, outcomes, and limits. Evidence cannot silently overwrite historical v1 or task-63 throughput logs.

- [ ] Predeclare controls and expected outcomes before running them.
- [ ] Execute normal/hard controls under the pinned image and save exact raw logs.
- [ ] Verify byte hashes, event chains, task/judge bindings, expected outcomes, and tamper rejection; replay in a fresh clone.
- [ ] Run the full pinned-image suite if engine source changed, inspect diff, and keep v2 release-ineligible pending independent review.
- [ ] Commit, push under the configured `greene80501` identity, and update draft PR #3 with measured results and limits.

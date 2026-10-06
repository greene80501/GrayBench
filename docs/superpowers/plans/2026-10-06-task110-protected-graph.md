# Task 110 Protected Graph Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a development-only, source-bound graph revision of QHE task 110 that rejects the two demonstrated native false passes while accepting valid Clifford circuit alternatives.

**Architecture:** Keep pinned native task bytes untouched. Construct a new public prompt and trusted private test from exact pinned source digests in a development module. Run it through protocol-4 `UpstreamJudge` in the pinned Docker image, then save an append-only authored-control log with exact case and judge identities. Do not register it as publication-ready or change the native headline.

**Tech Stack:** Python 3.12, Qiskit 2.4.2, Pydantic contracts, existing graph bridge, Docker, pytest.

**Spec:** `docs/reliability-evidence/task110-protected-graph-design.md`

## Global Constraints

- Preserve native normal/hard task bytes and their existing evidence.
- Publicly declare exactly `n` native `QuantumCircuit` values equivalent modulo global phase; no randomness or diversity claim.
- Candidate and trusted test remain in separate processes under the pinned image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
- Bind both pinned source digests and all private test, prompt, transport, extraction, and candidate bytes in the control log.
- Keep the result development-only pending independent task admission and transport review.

## Review Focus

- A valid phase-only variant should pass the native circuit bridge.
- A syntactically different circuit with the same tableau should pass.
- Empty and short lists should fail at positive `n`, while zero-length should pass for `n=0`.
- Wrong width, wrong Clifford, non-Clifford, and non-circuit outputs should fail without becoming infrastructure errors.
- A rewritten log or altered pinned source must not verify as the recorded trial.

---

### Task 1: Source-bound graph revision

**Files:** Create `docs/reliability-evidence/task110_protected_graph.py`; create `engine/tests/test_task110_protected_graph.py`.

**Interfaces:** `revised_task(source: JudgeTask) -> JudgeTask` validates pinned source digests and returns a new public prompt/private test; `Task110GraphJudge.configuration(source)` and `.evaluate(source, completion)` bind and execute that revision; `probes(source)` returns declared authored alternatives and mutants.

- [ ] Write tests for exact source binding, distinct normal/hard public prompts, graph judge configuration, and positive/negative controls.
- [ ] Run the tests and observe failure because the revision is absent.
- [ ] Implement the minimal revision and controls without changing `engine/src`.
- [ ] Run focused tests against the pinned cache and Docker image; fix failures and run Ruff.
- [ ] Commit with `[skip ci]` because the account's Actions quota is exhausted.

### Task 2: Reproducible authored-control evidence

**Files:** Extend the development module and tests; create `docs/reliability-evidence/artifacts/task110-protected-controls-2026-10-06/`.

**Interfaces:** `run_review` writes a new append-only JSONL log; `inspect_oracle_review` checks its chain, exact case metadata, source and declared judge identities; an additional test binds the development module hash.

- [ ] Write a failing test for exact expected control counts, recorded outcomes, source digest, and module hash.
- [ ] Generate the log in a new path and verify every declared expectation.
- [ ] Re-run verification and focused tests from a fresh clone; keep the result release-ineligible.
- [ ] Commit, push to PR #3, and update its description with the measured result and limits.

# Attempt-Bound Model Observations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind pre-request and post-response model metadata to each protocol 3.2 transport attempt without losing a returned answer when post-discovery fails.

**Architecture:** Keep protocol 3.1 behavior for historical runs. Add an append-only attempt-observation relation and bind it into existing event verification. The runner saves delivery first, then records post-discovery; reporting and judgment refuse a 3.2 attempt with missing or unstable evidence.

**Tech Stack:** Python 3.12, SQLite, Pydantic, httpx MockTransport, pytest.

**Spec:** [attempt-model-observation.md](../specs/2026-09-27-attempt-model-observation.md)

## Global Constraints

- Preserve protocol 3.1 and historical ledger evidence.
- Never retry or replace an already returned answer.
- Keep credentials out of the ledger and model observations provider-reported.
- Docker is unavailable locally; disclose skipped protected tests.

## Review Focus

- Process interruption between durable delivery and post observation.
- Drift or outage on the post request after a valid answer.
- A retry after rejected transport and its own post observation.
- Cross-run observation binding or event/row tampering.
- A direct ledger caller bypassing the campaign runner.

## Task 1: Relational and event identity

- [x] Add failing tests for a protocol 3.2 attempt's pre/post event bindings, missing post, and cross-run or tampered-row rejection.
- [x] Run the focused tests and confirm the intended failures.
- [x] Add protocol 3.2, the immutable binding table and event-row verification.
- [x] Rerun focused ledger tests and fix failures.

## Task 2: Campaign ordering and admission

- [x] Add failing MockTransport tests for pre/generate/post order, post drift/outage, and crash-like missing post with returned generation retained.
- [x] Run focused tests and confirm the intended failures.
- [x] Save delivery before post discovery, block later dispatch and judgment on incomplete exposure, and expose blockers in summary.
- [x] Run relevant offline Python 3.12 tests and Ruff.

## Task 3: Evidence and review

- [x] Document the exact guarantee and its limits in model-discovery evidence and reliability plan.
- [x] Verify event-chain tampering checks, a source-frozen 3.2 fixture, clean diff and credential scan.
- [ ] Obtain independent read-only review, address findings, commit under greene80501 and update draft PR.
- [ ] Verify GitHub CI; Docker-protected regression waits for Desktop recovery.

# Model-Observation Timing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make protocol 3.3 reject stale pre-observations and report late post-observations without losing returned answers.

**Architecture:** Add a frozen timing policy to 3.3 only. Compare bound ledger timestamps against attempt start and delivery finish; block dispatch or scoring on violations while preserving append-only observations. Keep 3.1/3.2 behavior and evidence unchanged.

**Tech Stack:** Python 3.12, Pydantic, SQLite, pytest/httpx MockTransport.

**Spec:** [model-observation-timing.md](../specs/2026-09-27-model-observation-timing.md)

## Global Constraints

- Prior protocol versions and evidence retain their original semantics.
- A timing failure leaves the provider response and generation intact and unscored.
- No billable model generation or Docker-protected claim during offline verification.

## Review Focus

- Host clock jumps forward or backward.
- Slow post-discovery after a valid answer.
- A pre-observation superseded by another process.
- Direct ledger calls bypassing the campaign runner.
- Cross-version comparisons or missing policies.

## Task 1: Frozen policy and preflight

- [x] Write failing protocol/setup/CLI and pre-dispatch age tests.
- [x] Confirm the intended failures, then implement 3.3 policy validation and preflight.
- [x] Run focused tests and Ruff.

## Task 2: Durable post timing and reporting

- [x] Write failing late/future post, retained generation, judgment/summary and retry tests.
- [x] Confirm the intended failures, then implement timing status and stop gates.
- [x] Run focused and full offline tests, inspect JUnit and source identity.

## Task 3: Review and integration

- [x] Document the assurance boundary, offline/protected results and remaining release gates.
- [x] Verify final diff, credential scan and independent read-only review.
- [ ] Commit as greene80501, push draft PR and verify CI; protected Docker regression passed.

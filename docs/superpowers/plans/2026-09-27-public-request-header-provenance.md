# Public Request Header Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze and audit the non-secret application headers GrayBench supplies with each model request, while preventing authentication headers from silently changing them.

**Architecture:** A focused header module canonicalizes standard JSON and adapter-declared public headers. `PreparedRequest` binds that map to its existing digest; transport checks it against the current adapter before sending, merges separately declared credential headers, and records the public map and credential header names in evidence. Historical requests without the new optional field remain readable with their old digest but cannot be newly dispatched.

**Tech Stack:** Python 3.12, Pydantic contracts, HTTPX, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-27-dual-track-qhe-design.md` (exact request and provenance rules, lines 70–95).

## Global Constraints

- Never persist credential header values or send them to candidate code.
- Do not change historical request identities or relabel historical ledgers.
- Reject drift before a new network dispatch; a mismatched request is not retried.
- Record headers GrayBench passes to HTTPX, without claiming packet-level capture or provider receipt.
- Keep GitHub Actions workflows disabled; verify locally with the pinned Python 3.12 image.

## Review Focus

- Case-varied duplicate header names must resolve to one canonical field or fail before dispatch.
- Authentication must not override `Content-Type`, `Accept`, `Accept-Encoding`, or an adapter's public extension.
- Plugin-declared public headers must reject credentials, CR/LF, and HTTP routing/framing overrides.
- A public-header change between planning and dispatch must stop before network I/O.
- Old serialized `PreparedRequest` objects must retain their exact digest and remain readable.

---

### Task 1: Versioned prepared header contract

**Files:** Create `engine/src/graybench/request_headers.py`; modify `engine/src/graybench/contracts.py`, `engine/src/graybench/providers.py`; test `engine/tests/test_providers.py`.

**Interfaces:** `freeze_public_headers(extra: Mapping[str, str]) -> dict[str, str]` returns lowercase, sorted standard and adapter public headers. `PreparedRequest.public_headers: dict[str, str] | None` is omitted from legacy JSON/digests when absent. `Adapter.public_headers(spec: ModelSpec) -> dict[str, str]` declares public extensions; `Adapter.credential_header_names` declares credential fields. `Adapter.request` populates the frozen full map.

- [ ] Write failing tests for frozen standard headers and changed request digest, legacy digest round-trip, public extension normalization, duplicate names, credential/framing headers, and CR/LF values.
- [ ] Run those tests and confirm each fails for the intended missing behavior.
- [ ] Implement the contract, helper, and adapter defaults with no secret values in the request artifact.
- [ ] Run focused tests and Ruff; commit this independently testable contract.

### Task 2: Transport enforcement and evidence

**Files:** Modify `engine/src/graybench/transport.py`; test `engine/tests/test_providers.py`, `engine/tests/test_model_discovery.py`, `engine/tests/test_campaign.py`.

**Interfaces:** `Transport.generate` compares the frozen public map with the supplied adapter's current declaration before I/O. `_exchange` sends that map plus only declared credential headers, records `request_public_headers`, its SHA-256 identity, and credential header names. Discovery uses the same header rules; old requests are read-only.

- [ ] Write failing HTTPX fixture tests for exact sent public headers, changed plugin header before dispatch, undeclared or overlapping auth headers, discovery headers, and no credential value in evidence.
- [ ] Run red tests; implement one checked merge path for generation and discovery.
- [ ] Confirm HTTP 5xx ambiguity and single-dispatch/recovery tests still pass; commit the transport step.

### Task 3: Source-bound verification and documentation

**Files:** Modify `engine/README.md`; create `docs/reliability-evidence/public-request-headers.md`.

- [ ] Document the precise assurance boundary: application-supplied headers, no proof of provider receipt, and unchanged historical artifacts.
- [ ] Run focused tests, changed-file Ruff/format, `git diff --check`, then the complete Docker-enabled test suite.
- [ ] Review the diff and tests, commit under `greene80501`, push to draft PR #3, and update its verification count while leaving workflows disabled.

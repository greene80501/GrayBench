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

- [x] Write failing tests for frozen standard headers and changed request digest, legacy digest round-trip, public extension normalization, duplicate names, credential/framing headers, and CR/LF values.
- [x] Run those tests and confirm each fails for the intended missing behavior.
- [x] Implement the contract, helper, and adapter defaults with no secret values in the request artifact.
- [x] Run focused tests and Ruff; commit this independently testable contract.

### Task 2: Transport enforcement and evidence

**Files:** Modify `engine/src/graybench/transport.py`; test `engine/tests/test_providers.py`, `engine/tests/test_model_discovery.py`, `engine/tests/test_campaign.py`.

**Interfaces:** `Transport.generate` compares the frozen public map with the supplied adapter's current declaration before I/O. `_exchange` sends that map plus only declared credential headers, records `request_public_headers`, its SHA-256 identity, and credential header names. Discovery uses the same header rules; old requests are read-only.

- [x] Write failing HTTPX fixture tests for exact sent public headers, changed plugin header before dispatch, undeclared or overlapping auth headers, discovery headers, and no credential value in evidence.
- [x] Run red tests; implement one checked merge path for generation and discovery.
- [x] Confirm HTTP 5xx ambiguity and single-dispatch/recovery tests still pass; commit the transport step.

### Task 3: Source-bound verification and documentation

**Files:** Modify `engine/README.md`; create `docs/reliability-evidence/public-request-headers.md`.

- [x] Document the precise assurance boundary: application-supplied headers, no proof of provider receipt, and unchanged historical artifacts.
- [x] Run focused tests, changed-file Ruff/format, `git diff --check`, then the complete Docker-enabled test suite after review fixes.
- [x] Review the diff and tests, commit under `greene80501`, push to draft PR #3, and update its verification count while leaving workflows disabled.

## Ruling during Task 2

Ruling: An injected HTTPX client can merge default headers, cookies, or query
parameters after GrayBench supplies its frozen map. Build one request, reject
unfrozen URL/header/body changes and request hooks before network I/O, and
send that same object with client authentication and redirects disabled. This
also records the checked non-secret HTTPX headers. The cost if this ruling is
wrong is rejection of a custom client that relies on implicit defaults; such
values must instead be declared in the public adapter header contract.

The independent review reproduced a custom adapter hiding `x-model-profile`
as a credential header, then varying its value without changing the prepared
digest or public evidence. Freeze credential field names in the prepared
request, allow only known credential fields, and require their values to be
the supplied secret (or its Bearer form for `Authorization`). The second
review found that credential presence and raw-versus-Bearer presentation could
still vary for one request. Freeze zero or exactly one emitted credential field,
require it when a credential is configured, and use one public value template
per field. This closes both reproduced bypasses while leaving provider-side
account semantics and installed plugin identity as explicit release gates.
The final review exposed a mutable-request interval after the ledger's digest
check: an adapter callback could alter the original header map or body, making
dispatch or evidence diverge. Snapshot the whole prepared request before
adapter callbacks, and separately copy the exchange body and header map before
authentication. A fixture asserts the wire and evidence use the original
values even when the adapter mutates its retained request reference.

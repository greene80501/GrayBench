# Provider Capability Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze exact model/endpoint capability evidence without claiming that a requested control was effective.

**Architecture:** Add an optional typed profile to `ModelSpec`; validate its evidence and exact identity before request preparation. Bind its digest in prepared requests and expose its qualified limits in reports. Omit absent fields so old artifacts remain byte-identical.

**Tech Stack:** Python 3.12, Pydantic 2, SQLite ledger, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-09-28-provider-capability-evidence.md`.

## Global Constraints

- No API keys, provider calls, or benchmark generations in this increment.
- Existing protocol, model-spec, and prepared-request identities remain stable when the optional profile is absent.
- A documented or probe-accepted setting is not an attested effective setting.
- Publication remains disabled pending independent provider and task qualification.

## Review Focus

- A profile for the wrong exact model or base URL must fail before request creation.
- A profile for another generation path must fail before a request artifact is written.
- A control citing a nonexistent or wrong-kind evidence reference must fail validation.
- A requested unknown, ignored, unsupported, or unlisted control must not be sent.
- Archived no-profile requests and ledgers must retain their identities and remain readable.

## Task 1: Contract and evidence validation

Files: `engine/src/graybench/contracts.py`, `engine/tests/test_provider_capabilities.py`.

- [x] Write failing tests for valid profiles, exact model/endpoint binding, invalid HTTPS URLs, evidence-reference mismatches, limits without evidence, and forbidden setting support.
- [x] Run those tests and confirm relevant failures.
- [x] Add versioned `CapabilityProfile` and `ControlSupport` contracts plus optional `ModelSpec.capability_profile` with absent-field omission.
- [x] Re-run focused tests and verify historical `ModelSpec` and protocol digests.

## Task 2: Request identity and adapter path

Files: `engine/src/graybench/contracts.py`, `engine/src/graybench/providers.py`, `engine/tests/test_provider_capabilities.py`.

- [x] Write failing tests for changed profile/request digests, path mismatch, ignored controls, and unchanged historical requests.
- [x] Run the tests to observe failures.
- [x] Bind an optional profile digest into `PreparedRequest` and check generation path in `Adapter.request`.
- [x] Re-run provider and campaign-plan tests.

## Task 3: Honest report and documentation

Files: `engine/src/graybench/ledger.py`, `engine/tests/test_provider_capabilities.py`, `engine/README.md`, `docs/reliability-evidence/provider-capability-evidence.md`.

- [x] Write failing tests for absent versus recorded profile reporting and unchanged `publication_eligible: false`.
- [x] Run the tests to observe failures.
- [x] Report the operator-supplied profile and explicit non-attestation of effective settings, with no release promotion.
- [x] Document operator workflow, limitations, and the checked official sources.
- [x] Run focused tests, Ruff, and the full pinned Docker-enabled suite; review the diff, commit as `greene80501`, push the draft PR, and leave GitHub Actions disabled.

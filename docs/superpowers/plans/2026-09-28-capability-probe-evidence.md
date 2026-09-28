# Capability Probe Evidence Implementation Plan

**Goal:** Replace bare accepted-request probe references in new campaigns with
self-contained, verified, non-benchmark transport artifacts.

**Spec:** `docs/superpowers/specs/2026-09-28-capability-probe-evidence.md`.

**Constraints:** Preserve old no-probe identities, never store a credential,
never claim effective settings from a successful probe, and keep publication
blocked. No live provider calls are needed for tests.

## Task 1: Typed record and offline verifier

Files: `engine/src/graybench/capability_probe.py`,
`engine/tests/test_capability_probe.py`.

- [x] Write failing tests for a valid fixed-prompt probe and for wrong model,
  endpoint, path, body, response hash, adapter code, and delivery state.
- [x] Add a versioned `CapabilityProbe` with a digest of the full non-secret
  record, a fixed public probe task, and `verify_accepted_probe`.
- [x] Reconstruct the request and parsed response; require exactly one
  successful return before a record can support `probe_accepted`.

## Task 2: One-call probe capture and CLI

Files: `engine/src/graybench/capability_probe.py`, `engine/src/graybench/cli.py`,
`engine/tests/test_capability_probe.py`.

- [x] Test one HTTPX-fixture call and exclusive output creation, including
  preservation of rejected/ambiguous diagnostics without qualification.
- [x] Implement `capability-probe MODEL_SPEC OUTPUT`, with no QHE prompt,
  no automatic retry, and no credential in the artifact.

## Task 3: Freeze evidence with campaigns

Files: `engine/src/graybench/campaign_setup.py`,
`engine/src/graybench/native_campaign.py`,
`engine/src/graybench/protected_campaign.py`, `engine/src/graybench/cli.py`,
`engine/src/graybench/ledger.py`, and focused tests.

- [x] Test bare/extra/duplicate digest rejection, same-value control coverage,
  archived JSON round-trip, and no-probe historical omission.
- [x] Add optional embedded probe records to all three campaign setups, a
  repeated `--capability-probe` input to all three plan commands, and
  verification at plan, execution-context, and ledger boundaries.
- [x] Report locally verified versus missing/invalid probe artifacts as a
  separate provider-capability status and blocker, without release promotion.

## Task 4: Documentation and verification

Files: `engine/README.md`,
`docs/reliability-evidence/provider-capability-evidence.md`.

- [x] Explain the command, bundle, confidence limit, and operator workflow.
- [x] Run focused tests, changed-file Ruff, historical identity checks, and
  the full pinned Docker-enabled engine suite.
- [ ] Review the diff, commit as `greene80501`, push draft PR #3, update its
  description, and confirm GitHub Actions remain disabled.

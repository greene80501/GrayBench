# Adapter Code Provenance Implementation Plan

**Goal:** Detect a changed installed adapter implementation before discovery or
generation and bind its non-secret code manifest into new campaign identity.

**Spec:** `docs/superpowers/specs/2026-09-28-adapter-code-provenance-design.md`.

**Constraints:** Preserve historical JSON/digests; never claim that a local
hash proves plugin honesty or provider behavior; keep Actions workflows
disabled; use the current isolated `rewrite/auditable-core` worktree.

## Task 1: Compute a bounded adapter code manifest

**Files:** Create `engine/src/graybench/adapter_provenance.py`,
`engine/tests/test_adapter_provenance.py`.

**Interface:** `adapter_code_manifest(provider: Adapter) -> dict` and
`adapter_code_digest(provider: Adapter) -> str`. Exact built-in classes use
the GrayBench source digest. Registered class entry points include entry-point
and distribution metadata and hash the top-level package tree. Directly
provided development subclasses hash their defining module only. The manifest
contains logical names and hashes, no absolute paths or bytes. Limit to 4,096
files and 64 MiB; reject unstable, missing, symlinked, or unreadable input.

- [x] Write failing tests for built-in versus subclass classification,
  package-file edit changing the digest, logical-path-only output, and
  rejected missing/symlink/oversize sources.
- [x] Run the new tests red. Implement the smallest deterministic manifest.
- [x] Run focused tests and changed-file Ruff/format; commit.

## Task 2: Bind new prepared requests and transport

**Files:** Modify `engine/src/graybench/contracts.py`, `providers.py`,
`transport.py`; extend `engine/tests/test_adapter_provenance.py`.

**Interface:** `PreparedRequest.adapter_code_digest: str | None` is omitted
when absent. `Adapter.request` populates it. `Transport.generate` rejects a
missing or changed adapter digest before any network I/O. Discovery records
the adapter digest in each observation and accepts an optional frozen expected
digest that it checks before I/O.

- [ ] Write failing tests for prepared digest change, historical round-trip,
  changed provider file before generation, and changed file before discovery.
- [ ] Run red tests, implement the contract and transport check, then run the
  affected provider/discovery/campaign suite; commit.

## Task 3: Bind campaigns and document assurance

**Files:** Modify `Protocol`, `campaign_setup.py`, `native_campaign.py`,
`protected_campaign.py`, `campaign.py`, and `model_discovery.py`; add focused
tests and `docs/reliability-evidence/adapter-code-provenance.md`.

**Interface:** Optional `Protocol.adapter_code_manifest` is omitted for
historical manifests. New builders populate it from the same adapter that
renders requests and verify every new request's adapter digest. Creation and
resume compare the current manifest with the protocol; observation passes its
expected digest to discovery. Historical protocols remain readable but cannot
claim this new provenance.

- [ ] Write failing tests for new setup binding and pre-network drift,
  including discovery, and historical protocol identity preservation.
- [ ] Run red tests; implement the new checks without relabeling old runs.
- [ ] Document exact coverage and limits. Run focused tests and Ruff/format;
  commit.

## Task 4: Complete verification and PR

- [ ] Run the complete pinned Python 3.12/Qiskit Docker-enabled engine suite
  and `git diff --check`.
- [ ] Obtain independent read-only review of manifest coverage, drift checks,
  secret/path leakage, and historical identity. Fix Important findings with
  failing tests and rerun the suite if source changes.
- [ ] Push under `greene80501` to draft PR #3, update the PR description with
  the exact local result, and verify both workflows remain disabled.

## Review focus

The reviewer should probe namespace packages, symlink/path escape, editable
installs, dynamic helper imports, plugin classes sharing a built-in name,
mutable manifest objects, and plugin code changing between planning and
network send. Any unsupported input must fail or be explicitly labeled
development-only; it must never silently claim full package coverage.

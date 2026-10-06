# Task 139 protected value revision

**Goal:** Add a development-only, source-bound protected value revision for QHE task 139 that rejects the known empty-answer false pass while accepting mathematically equivalent Schmidt decompositions.

**Scope:** Keep pinned native prompts/tests unchanged. Publish no model score. Use Python 3.12 and the existing protected runner and admission model.

**Design:** [Task 139 protected value design](../../reliability-evidence/task139-protected-value-design.md).

## Tasks

- [x] Write focused failing tests for the plain-Python Schmidt oracle: basis/product, entangled, complex global phase, reordered terms, degenerate rotations; reject empty/fixed/missing/nonorthogonal/bad-weight/wrong-order values and malformed data.
- [x] Implement only the trusted value condition and freeze the 240 ordered-partition/state cases with validation tests that catch omissions, replacements, and reorderings.
- [x] Write failing integration tests for normal/hard pinned-source ancestry, public JSON contract, registry dispatch, manifest binding, and real Docker runner outcomes; implement the protected task and registry plumbing.
- [x] Freeze independent positive and negative candidate controls, run them on both suites under the pinned image, inspect the result chain, and record exact limitations and admission status.
- [x] Run full engine tests and lint, review the diff, commit as the user's GitHub identity with `[skip ci]`, and update draft PR #3 without triggering GitHub Actions.

## Rulings

- This is a value revision, not a replacement native score. Numerical acceptance uses explicit absolute tolerance `1e-8`; nonzero weights have no arbitrary lower bound. The case domain is frozen and public to candidates, so passing it establishes these calls only, not universal mathematical correctness.

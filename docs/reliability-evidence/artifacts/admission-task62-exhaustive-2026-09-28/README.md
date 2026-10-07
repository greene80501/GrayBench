# Task-62 exhaustive-v2 admission successor, 2026-09-28

This bundle succeeds the [task-62 current-source v1 bundle](../admission-task62-current-2026-09-28/README.md).
Its first three control logs are byte-identical to that predecessor. It
replaces only the task-62 log with the [exhaustive-v2 controls](../task62-protected-exhaustive-2026-09-28/README.md).
The old v1 log remains in the predecessor, so its observations are not
rewritten. The new 302-card inventory advances the current finding registry
and engine source digest, then rebinds the two task-62 cards to the exact v2
judge and nine authored controls per suite. It does not resolve either known
task-62 finding or claim independent review.

From `engine/`, with the SHA-256-pinned normal and hard parquet files in
`CACHE`, verify the exact saved bytes and recomputed audit:

```sh
uv run --locked graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-task62-exhaustive-2026-09-28 CACHE
```

The [manifest](manifest.json) pins the inventory, four logs and audit by
exact bytes and SHA-256. Its digest is
`4855b7d3f5c870c543f2b83b129387c04b902b1dd65d67594b2ba9d2722a5502`;
the recomputed audit digest is
`a3a1ee09ba776966d1e4c10a32280c5391961a3339d7ead81831071f730481d3`.
The [builder](../../refresh_task62_admission_exhaustive.py) reproduced all
seven pinned files byte-for-byte in a second directory. It requires the
predecessor to verify, confirms that its finding registry is historical,
reconstructs both exact v2 judges and all 18 controls, and recomputes the
source-bound admission links.

The audit has 60 authored controls on ten cards, 42 bound to declared
protected judges, eight historical upstream false passes and 292 cards
without controls. Both task-62 cards have three positive and six negative
control links under v2. Across the inventory, 96 card-level known findings
have no resolution evidence, no requirement cites an independently verified
oracle-case fixture, and no card has reviewer attestations. The first three
logs still represent earlier source revisions. `publication_eligible` is
false; this is neither an admitted benchmark nor a model score.

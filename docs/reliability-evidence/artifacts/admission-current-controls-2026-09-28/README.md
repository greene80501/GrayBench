# Current-source protected admission successor, 2026-09-28

This bundle succeeds the
[task-62 exhaustive admission snapshot](../admission-task62-exhaustive-2026-09-28/README.md).
It keeps the first two upstream task-0/1 logs byte-identical and replaces only
the task-2/20 and task-62 protected control logs with the verified
[current-source set](../protected-controls-current-source-2026-09-28/README.md).
The old protected logs remain in the predecessor. The 302-card inventory
changes its source digest and four task-2/20 judge digests. Both task-62 judge
digests remain identical because their exact judge manifests did not change.
Every other card field is preserved.

From `engine/`, with the exact pinned normal and hard parquet cache:

```sh
uv run --locked graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-current-controls-2026-09-28 CACHE
```

The [manifest](manifest.json), SHA-256
`783726d53930f1210be472ff34b514110fb17c46fdb49efdc2da3754641b5571`,
pins seven files by exact bytes and hashes. The recomputed [audit](audit.json)
has SHA-256 `32b74ec26bf5256e15a3140da619cabf07a08ee010f75a64cd1bef6c5a2fa21c`.
The [builder](../../refresh_admission_current_controls.py) verified the
predecessor, control headers, source digest, six declared judges, case metadata,
requirement links and the task-62 omitted-input miss. Two independent builds
from the same fixed inputs produced identical bytes for all seven pinned files.

The verifier reports 60 authored controls on ten cards, 42 bound to declared
protected judges, all 42 matching the inventory source, and zero bound
controls from a different source. Eight upstream false passes and 292 cards
without controls remain. No oracle-case fixture or independent review is
verified; 96 card-level known findings remain unresolved.
`publication_eligible` is false. This bundle is not an admitted benchmark or
a model score. A later engine-source edit will make this inventory historical
relative to that engine, and the verifier will report the mismatch.

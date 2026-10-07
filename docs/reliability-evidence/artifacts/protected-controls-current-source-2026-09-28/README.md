# Current-source protected value controls, 2026-09-28

These two logs record predeclared, authored candidate controls under one engine
source digest, `1515370b867b0160d6da999ac908912ae24337aa60746a7f705cb83dd176a748`,
and pinned Python 3.12/Qiskit image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
The [manifest](manifest.json), SHA-256
`154da70bbd61737bbaafd10458932c2b2ce672649d6ca6f632184b889d405bae`,
fixes both log names, byte counts and hashes.

From `engine/`, with the exact pinned normal and hard parquet cache:

```sh
uv run --locked graybench oracle-review-inspect ../docs/reliability-evidence/artifacts/protected-controls-current-source-2026-09-28/task2-20.jsonl CACHE
uv run --locked graybench oracle-review-inspect ../docs/reliability-evidence/artifacts/protected-controls-current-source-2026-09-28/task62-exhaustive-v2.jsonl CACHE
```

The task-2/20 log verifies 24 of 24 outcomes (12 positive, 12 negative) across
both suites. The task-62 exhaustive-v2 log verifies 18 of 18 (six positive,
12 negative). In both suites, the omitted-input mutant fails only on
`width-4-state-1000-basis-0000` among 1,364 frozen cases. The
[admission successor](../admission-current-controls-2026-09-28/README.md)
checks the manifest and both logs before binding them to task cards.

These are local, unsigned value-condition observations. They do not establish
native Qiskit circuit equivalence, independent oracle review, or a model score.

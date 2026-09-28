# Frozen task-finding registry, 2026-09-28

This bundle succeeds the [task-2/20 binding bundle](../admission-bindings-2026-09-28/README.md). Its three control logs are byte-identical to that bundle. The 302-card inventory retains the four authored task-2/20 contract and judge bindings and adds the [task-62 fixed-oracle finding](../task62-fixed-oracle-2026-09-28/README.md) to both normal and hard cards. The new schema-3 inventory embeds the finding registry and its digest. Earlier schema-2 inventories still verify against their historical registry; they are not silently rewritten when a new finding is discovered. `admission-refresh-findings` performs the explicit migration and refuses to remove a historical finding.

From `engine/`, with the locked environment and both SHA-256-pinned QHE parquet files in `CACHE`, run:

```sh
uv run --locked graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-findings-2026-09-28 CACHE
```

[`manifest.json`](manifest.json) fixes every evidence file by exact byte length and SHA-256. The verifier checks these bytes, the frozen inventory against pinned task ancestry, all three control logs, and a byte-for-byte recomputation of the audit. The inventory model digest is `a7854800a714a4aed491d02174397910bca5cffde8ae27f258c86f0c7e843ec2`; the audit file SHA-256 is `2507b4f75cc6c86a5cc6b5653c8f768f10f4d88571801123a34a1da981e316a4`.

The audit reports 42 controls on eight cards, 24 matching the four bound protected judges, eight upstream false passes, and 294 cards with no controls. No new task-62 candidate control is included here: its separate native probe establishes a concrete false pass, not a protected-task admission. All cards still need adequate fixture review and independent review, among other gates. The observations are locally authored and unsigned. `publication_eligible` is `false`; this bundle is neither a model score nor an admitted benchmark release.

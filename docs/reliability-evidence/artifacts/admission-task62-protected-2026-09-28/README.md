# Task-62 protected admission bindings, 2026-09-28

This bundle succeeds the [schema-3 finding inventory](../admission-findings-2026-09-28/README.md). Its prior three logs are byte-identical, and a fourth log adds the [protected BB84 value controls](../task62-protected-value-2026-09-28/README.md). The 302-card [inventory](inventory.json) binds the normal and hard task-62 cards to their revised public amplitude contracts and exact protected judge manifests. The cards cite three authored correct alternatives and five authored wrong answers per suite; the [audit](audit.json) confirms all 16 links match the declared judge and expected outcome. The pinned native fixed-input false-pass finding remains on both cards.

From `engine/`, with both SHA-256-pinned QHE parquet files in `CACHE`, run:

```sh
uv run --locked graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-task62-protected-2026-09-28 CACHE
```

[manifest.json](manifest.json) fixes the inventory, audit and four control logs by exact byte length and SHA-256. The verifier re-inspects each log and recomputes the entire schema-5 audit byte for byte. The deterministic [builder](../../build_task62_admission_bundle.py) reconstructs the current task-62 judges and probes, checks the predecessor bundle and source identity, and writes an exclusive bundle. The shorter `inventory.json` and `audit.json` filenames also work under the Windows path limits of this checkout.

The verified audit has 58 controls on ten cards, 40 linked to predeclared protected judges, eight upstream false passes and 292 cards without controls. For task 62, `oracle_cases_missing`, `known_findings_unresolved` and `independent_review_missing` remain explicit blockers. Task-2/20 controls and bindings were produced under older judge source bytes; this bundle preserves them as historical observations and does not claim they certify the current source revision. All controls are locally authored and unsigned. `publication_eligible` is `false`; this is no model score or independently admitted benchmark.

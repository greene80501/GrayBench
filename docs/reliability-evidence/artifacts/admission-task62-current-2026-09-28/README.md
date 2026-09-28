# Task-62 admission source refresh, 2026-09-28

This bundle succeeds the [earlier task-62 admission bundle](../admission-task62-protected-2026-09-28/README.md). It preserves the first three control logs byte for byte and replaces only the task-62 review log with the [current-source rerun](../task62-protected-current-source-2026-09-28/README.md). The builder verifies both bundles and requires all 34 task-62 event payloads to match after excluding only timestamps and the engine source manifest. The 302 admission cards are unchanged except for the inventory's current engine source digest.

From `engine/`, with the SHA-256-pinned QHE parquet files in `CACHE`, verify this bundle:

```sh
uv run --locked graybench admission-bundle-verify ../docs/reliability-evidence/artifacts/admission-task62-current-2026-09-28 CACHE
```

The [manifest](manifest.json) pins the inventory, audit and four logs by exact bytes and SHA-256. The [builder](../../refresh_task62_admission_source.py) writes an exclusive bundle after recomputing and verifying the audit. The audit still reports 58 controls on ten cards, 40 linked to predeclared protected judges, eight historical upstream false passes, and 292 cards without controls. The task-62 log is bound to source digest `bcd6b4379ee62c3c8a15be4d6368e961467ab7506d6787a39ede36d60782a70d`. The other three logs remain historical observations from earlier source revisions and do not certify the current judge source.

The controls are locally authored and unsigned; task contracts, oracle fixtures, known findings, and independent review remain open release gates. `publication_eligible` is false. This bundle is neither an admitted benchmark nor a model score.

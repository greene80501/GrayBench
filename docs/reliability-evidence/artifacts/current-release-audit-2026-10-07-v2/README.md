# October 7 audit after the explicit nesting condition

The [report](report.json) reruns the read-only [release audit](../../current_release_audit.py) on engine source `c473a44e184707353b3c80ad73c0aed95a4c81f7e0da76e9f8b3b1028de9712a`. It is 1,446 bytes, SHA-256 `790eb51aa7f8d09bfda2199c1a9478117b54f30eb351a4ad6e0e984c8b3e24e3`. The [earlier October 7 report](../current-release-audit-2026-10-07/README.md) is preserved at its own source identity.

All five built-in adapters preserve the exact original public prompt across 302 pinned normal/hard records: 1,510 local request preparations. This checks original prompt rendering on the current engine; it does not execute candidates, contact providers or qualify effective model settings. Task 117 v2's unchanged revised requests and distinct resource identities are checked separately in the engine tests.

The audit deliberately uses the unchanged [historical admission inventory](../admission-task139-current-2026-10-06/README.md), source `0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924`. It records 302 cards, eight with protected contracts/judges, zero independent reviews and zero cards without structural admission blockers. These are historical inventory counts, not a refreshed claim of current coverage. `inventory_matches_current_source` and publication eligibility are both false. The 143-task offline subset still excludes eight service-dependent tasks from each 151-task suite.

From `engine/`, reproduce with:

```sh
uv run --extra dataset python ../docs/reliability-evidence/current_release_audit.py --cache CACHE --inventory ../docs/reliability-evidence/artifacts/admission-task139-current-2026-10-06/inventory.json
```

Compare parsed JSON because terminal newline conventions differ across platforms. This evidence does not establish oracle quality, complete resource-domain support, isolated runtime behavior or any model score. No historical inventory, control log or model answer was relabeled.

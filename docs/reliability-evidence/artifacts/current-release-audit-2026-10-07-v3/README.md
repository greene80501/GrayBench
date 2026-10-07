# October 7 audit after the matrix conditions

The [report](report.json) reruns the read-only [release audit](../../current_release_audit.py) on engine source `4770bfec384cfe4f52a1fcd4cb832bed65f012a9234462f4dd25f531ab8cf90d`. Its 1,446 bytes have SHA-256 `00ded9b0e4128edc7af08a057ffe77fe1961071135575bf1267154b2531438e4`. The [earlier nesting-condition audit](../current-release-audit-2026-10-07-v2/README.md) remains bound to its own source.

All five built-in adapters preserve the exact original public prompt across 302 pinned normal/hard records: 1,510 local request preparations. This checks rendering without contacting a provider or executing a candidate. The three new matrix conditions' revised requests and separate resource identities are checked by engine tests described in [their development evidence](../../matrix-semantics-development.md).

The audit deliberately uses the unchanged [historical admission inventory](../admission-task139-current-2026-10-06/README.md), source `0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924`. It records 302 cards, eight with protected contracts/judges, zero independent reviews and zero cards without structural admission blockers. These counts are historical coverage, not a refreshed inventory of the new development conditions. The inventory does not match the current source; publication eligibility remains false. The offline cohort still excludes eight service-dependent families per suite, leaving 143 tasks each.

From `engine/`, reproduce with:

```sh
uv run --extra dataset python ../docs/reliability-evidence/current_release_audit.py --cache CACHE --inventory ../docs/reliability-evidence/artifacts/admission-task139-current-2026-10-06/inventory.json
```

Compare parsed JSON when terminal newline conventions differ. This evidence does not establish oracle adequacy, complete-domain resource support, isolated runtime qualification, effective provider settings or model scores. Historical inventories and controls are unchanged.

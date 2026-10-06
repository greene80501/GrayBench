# Current-source release audit after request capture v2

The adjacent [report](report.json) records a read-only audit at Git revision
`e083012177ff67843276986cae14711b428da991`, with engine-source digest
`caff2a249c236f91c9073694e4812166687fcc2fdeda32bdb2db7cc2fbb29f14`.
The [audit script](../../current_release_audit.py) has SHA-256
`2dec803de6e3cd68b273c4006bff7d2dd098b623671d5a0226db0700c2571ca2`;
the 1,425-byte report has SHA-256
`c437f3ea0f05b09352f17755904bb0d9bd6e5128fc452381a116dbb759413cad`.
This is a new snapshot; the [earlier audit](../current-release-audit-2026-10-05/README.md)
remains preserved at its original source revision.

All five built-in adapter routes prepared the exact pinned public prompt for
all 302 normal/hard tasks, yielding 1,510 request preparations in total.
The audit does not call a provider or Docker. The 302-card inventory still has
only six bound protected judges, zero independent reviews, and zero cards
without structural blockers. Its historical source digest does not match this
engine source. The protected-value registry still covers only task families
2, 20, and 62; the declared offline subset remains 143 tasks per suite.
`publication_eligible` is false. The new request capture version improves
client-side attempt provenance but does not resolve task admission or oracle
adequacy.

Reproduce from `engine/` with the verified pinned cache and historical
admission inventory:

```powershell
uv run --locked --extra dataset --extra qiskit --group dev python ../docs/reliability-evidence/current_release_audit.py --cache ../../../outputs/pinned-qhe-cache --inventory ../docs/reliability-evidence/artifacts/admission-current-controls-2026-09-28/inventory.json > current-report.json
```

Compare the output bytes or parsed content to `report.json`. Request manifest
digests depend on source identity and will change when relevant source changes.
The same command at revision `e083012` in a separate clone produced a
byte-identical report with the SHA-256 above.
This audit does not certify the 151-task suites, provider effective settings,
container judgment, independent reproducibility, or a model ranking.

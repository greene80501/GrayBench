# Release audit with current-source admission evidence

The adjacent [report](report.json) reruns the read-only
[audit script](../../current_release_audit.py) against the [current-source
admission successor](../admission-current-controls-2026-10-05/README.md).
The report is 1,424 bytes with SHA-256
`e236bab36e749720d243f92cc9652f6a66a57da52521bffb4dc26906cc40c307`.
Its engine and inventory source digests both equal
`344f5f501a33d10d245183289f234c5e8af083a5272b96f9ed140094f017b802`.
The earlier [v3 audit](../current-release-audit-2026-10-05-v3/README.md)
remains preserved and shows why the historical inventory was stale.

All five built-in adapter routes prepared the exact public prompt for all
302 pinned normal/hard tasks, totaling 1,510 request preparations. The
inventory now matches the running engine source and has six cards with bound
protected semantic judges. It still has zero independent reviews and zero
cards without structural blockers. `publication_eligible` remains false.

From `engine/`, reproduce using the verified pinned cache:

```powershell
uv run --locked --extra dataset python ../docs/reliability-evidence/current_release_audit.py --cache <pinned-cache> --inventory ../docs/reliability-evidence/artifacts/admission-current-controls-2026-10-05/inventory.json > new-report.json
```

This audit makes no provider or Docker call. It verifies local prompt
preparation and admission bookkeeping, not provider receipt, oracle adequacy,
independent review, or a model ranking.

The same command at a separate checkout of `c3bc35a` produced a byte-identical
report with the SHA-256 above.

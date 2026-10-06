# Current-source release audit after Docker recovery

The adjacent [byte-preserved report](report.json) is a read-only audit at Git
revision `f20ed6870fccc5096a2c63a48f9b1257ba5c7168` with engine source digest
`344f5f501a33d10d245183289f234c5e8af083a5272b96f9ed140094f017b802`.
The [audit script](../../current_release_audit.py) has SHA-256
`2dec803de6e3cd68b273c4006bff7d2dd098b623671d5a0226db0700c2571ca2`.
The 1,425-byte report has SHA-256
`d44bf43edfa9140721fbc32b5ddf32cde739d736bc07a46307fa3a13c271fb72`.
The earlier source-bound [audit](../current-release-audit-2026-10-05-v2/README.md)
remains preserved.

All five built-in adapter routes prepared the exact pinned public prompt for
all 302 normal/hard tasks, totaling 1,510 request preparations. The 302-card
historical admission inventory has six bound protected semantic judges, zero
independent reviews and zero structurally clear cards. Its source digest
`1515370b867b0160d6da999ac908912ae24337aa60746a7f705cb83dd176a748`
does not match this audit's engine source. The current value-task registry
covers task families 2, 20 and 62, and the declared offline subset remains
143 tasks per suite. `publication_eligible` is false.

From `engine/`, reproduce using the verified pinned cache and the exact
historical inventory:

```powershell
uv run --locked --extra dataset python ../docs/reliability-evidence/current_release_audit.py --cache <pinned-cache> --inventory ../docs/reliability-evidence/artifacts/admission-current-controls-2026-09-28/inventory.json > new-report.json
```

Compare the output bytes with `report.json`. This audit makes no provider or
Docker call and does not certify prompt delivery, effective provider settings,
oracle correctness, independent review, or a model ranking. The separately
preserved [current-source value controls](../protected-current-controls-2026-10-05/README.md)
verify 42 authored outcomes but do not silently update the historical
admission inventory.

The same command at a separate clean checkout of `cd81e6c` produced a
byte-identical report with the SHA-256 above. The script bytes also matched
their recorded SHA-256 in that checkout.

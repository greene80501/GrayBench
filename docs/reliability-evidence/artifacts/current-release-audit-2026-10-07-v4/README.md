# October 7 audit after the protected evolution value condition

The [report](report.json) reruns the read-only
[release audit](../../current_release_audit.py) on engine source
`1b845366bfc60a76f91b771f353ed58da91815cf26e5b70f5688c4f1232ae40f`.
Its 1,468 bytes have SHA-256
`5bd97f38ed29ed1c384e5658b382d05e6219756b90726fbff3d6a33fb3f3f88c`.
The [previous audit](../current-release-audit-2026-10-07-v3/README.md)
remains bound to its own source and is unchanged.

All five built-in adapters preserve the exact original public prompts across
302 pinned normal/hard records: 1,510 local request preparations. No provider
request or candidate execution occurs. The registry now contains separate
value revisions for families 2, 20, 62, 116 and 139. Revised task-116 requests
and cohort reconstruction are checked by its focused tests, rather than this
original-prompt audit.

The preserved [historical inventory](../admission-task139-current-2026-10-06/README.md)
has 302 cards, eight protected contracts/judges, zero independent reviews and
zero cards without structural admission blockers. Its source differs from this
engine source, and these historical counts do not include the newly developed
conditions. Publication eligibility remains false. Each offline suite still
contains 143 of 151 tasks after excluding eight service-dependent families.

From `engine/`, reproduce with:

```sh
uv run --locked --extra dataset python ../docs/reliability-evidence/current_release_audit.py --cache CACHE --inventory ../docs/reliability-evidence/artifacts/admission-task139-current-2026-10-06/inventory.json
```

Compare parsed JSON if terminal newlines differ. This checks source, task
ancestry and request preparation; it does not certify oracle adequacy,
container isolation, effective provider settings, admission or model scores.

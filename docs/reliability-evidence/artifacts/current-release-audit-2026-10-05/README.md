# Current-source release-gate and request-rendering audit

The adjacent [report](report.json) is a read-only observation of engine source
`f7cd2fd1ca66fb782033b2e10aa28bed7b0baf525f298ae8af198eb714fb3625`.
The [audit script](../../current_release_audit.py) has SHA-256
`2dec803de6e3cd68b273c4006bff7d2dd098b623671d5a0226db0700c2571ca2`;
the report has SHA-256
`63903e3f960c02d43bc245e7a7d903baef01d4276576af117a5ee09e3a3f9acb`.
It reads the content-pinned 151 normal and 151 hard records and the historical
source-bound admission inventory. It makes no model API or Docker call.

For each of five built-in adapters, all 302 prepared request bodies contained
the exact public prompt in the adapter's expected user field and no additional
instruction or setting. The report retains one request-manifest digest per
adapter. This checks GrayBench's client-side preparation only; it does not
attest the provider's internal prompt template, effective sampling settings,
model weights or response behavior.

The inventory has 302 cards, six with bound public contracts and protected
judges, none with an independent review, and none without structural admission
blockers. Its source digest differs from the current engine source, so the
historical controls cannot be promoted silently. The current protected-value
registry covers only task families 2, 20 and 62. The native offline subset is
143 tasks per suite, excluding eight external-service tasks. These facts rule
out a certified complete score under the current source; they do not invalidate
historical observations.

Reproduce from `engine/` with the verified pinned cache:

```powershell
uv run --locked --extra dataset --extra qiskit --group dev python ../docs/reliability-evidence/current_release_audit.py --cache ../../../outputs/pinned-qhe-cache --inventory ../docs/reliability-evidence/artifacts/admission-current-controls-2026-09-28/inventory.json > current-report.json
```

Compare the output bytes or parsed content to `report.json`. Request digests
will change if adapter source or public request identity changes; source drift
is reported, not treated as a failed historical inventory. This audit does not
replace per-task oracle review, protected Docker controls, independent machine
reproduction, live provider probes or full predeclared model campaigns.

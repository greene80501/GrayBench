# Bell-shot diagnostic evidence

This bundle supports the [sampling review](../../bell-shot-diagnostics.md) for
pinned normal/hard Tasks 1, 14, 15 and 31. Original tasks and engine runtime code
are unchanged. Engine source remains
`cb27140691d9c4e5fbd794cc9d02bc701790d7eacb46ec06d42353a8dcc3181d`.

`plan.json` was written exclusively before execution. It binds all eight full
and public task identities, exact check text and function AST identities, dataset
pins, all 113 engine source files, this diagnostic's raw bytes, 30 trusted-data
fixtures with declared outcomes, shot counts and conditional assumptions.
`report.json` records 60 normal/hard data trials: 28 pass, 26 fail and six errors,
all matching predeclared check behavior. A passing fixture is not a correct
sampler implementation; invalid count and shot data are intentionally retained.

Two independent exact binomial computations agree with both pinned Task1 checks
across all 20,820 nonnegative count-vector trials for shots 1 through 128, 1000
and 1024. Small ordered-sequence enumeration and Pascal-row tests independently
calibrate the arithmetic. Task14's all-identical 100-shot ideal event has exact
probability `2^-99`. Task15's rational `(1-q)^n` records describe only no-outside
events, not a calibrated noise model or full check rejection probability.
Task31 seed behavior remains explicitly unattested.

`runtime-source-review.json` records immutable upstream commits and raw source
hashes for generic Runtime options, local-service delegation and BackendSamplerV2
defaults. This document-only source review is separate from the statistical plan
and does not attest installed behavior or seed execution.
Its root-lock digest describes the raw main working copy, including local newline
encoding; it does not claim identical root-lock bytes in every checkout.

Reproduce from `engine/` with the locked Python 3.12 environment and verified
pinned cache:

```sh
python ../docs/reliability-evidence/bell_sampling_diagnostic.py CACHE ../docs/reliability-evidence/artifacts/bell-shot-diagnostics-2026-10-07/report.json --check
```

For new evidence, select an unused output directory. Plan/report creation is
exclusive; an interrupted or existing experiment is not overwritten or silently
rebound. `--check` requires exact source and report recreation. `focused.xml`
records 28 passed related tests with zero failures/errors/skips. Full and clean
results, when recorded, retain their actual scope and source binding.

The full main-checkout regression passes 1,859 tests with 297 skips and zero
failures/errors in 642.93 wall seconds. Its 48 warnings are original Qiskit
Diagonal deprecations. Python 3.12.14 and the locked Qiskit 2.4.2 host environment
were used with the verified pinned cache. Ruff lint and formatting pass for 261
files. No immutable test images were configured; isolated groups remain skipped.

The read-only AI review found no actionable defects and independently checked
all eight sources, pointwise count-vector agreement, exact arithmetic and
fail-closed replay. The extra generic-Bell cases were also rechecked. AI review
does not establish independent human task admission.

No actual sampler, transpiler, Docker, native build or model execution was
performed, and no model-provider API was called. Complete check bodies run only
with trusted fixture callbacks;
external imports and candidate implementations are excluded. Conditional ideal
arithmetic is not an observed sampler failure rate or a full native false pass.
`publication_eligible`, `runtime_qualified` and `independent_human_admission`
remain false. No strengthened task or modified threshold is supplied here.

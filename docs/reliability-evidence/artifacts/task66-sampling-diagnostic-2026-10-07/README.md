# Task66 sampling diagnostic evidence

The [diagnostic](../../task66-sampling-diagnostic.md) quantifies variability of
the private count thresholds and the inability of this observable to establish
an explicit symmetric W-state phase convention. Original tasks and scores remain
unchanged; no replacement judge is supplied.

[plan.json](plan.json) was exclusively written before control execution. It binds
both exact ancestor/public/test digests, all seven assertion AST nodes, nine
authored circuit expectations, six count records, script bytes and engine source.
[report.json](report.json) reproduces exactly. Its 108 assertion trials preserve
every count outcome: 36 passes, 54 assertion failures and 18 errors in the original
outside-support assertion message. The error is `result.keys()` on a circuit;
it is not mislabeled as a successful semantic rejection.

All nine circuit fixtures have the same independently specified ideal probabilities.
Four are the symmetric W state up to global phase; the other five have fidelities
1/9, 1/9, 1/9, 5/9 and zero. Numerical SDK calibration errors are below `1e-14`.
The last state is orthogonal to the explicit symmetric W state. Original phase
intent still requires adjudication; no full native false pass is claimed.

Two integer derivations agree on the exact probability of all three ideal iid
counts lying in 300..400 inclusive with total 1024. Independent tests enumerate all
ordered three-label shot sequences for n=0..7 across every inclusive bound pair.
Exact fractions are saved; ideal rejection is **0.7756595364539097%** per run.
The hypothetical independent 20-replay any-rejection approximation is 14.42155%.
Neither is an observed real sampler failure rate. No sampler was executed.

Only trusted authored host circuits and exact assertion AST slices execute.
Candidate invocation, imports, transpiler, sampler and job-result collection
are excluded. No API/model/Docker calls, isolated runtime qualification, human
admission, repaired scores or universal correctness claims are made.

Environment: Python 3.12.14, Qiskit 2.4.2, NumPy 2.2.4.
Unchanged engine source digest:
`3b137cbcf666d377d0347ba0eca6a77b9d07e06eaf712e93cb514764c9bae91e`.

From `engine/` at these exact engine/script bytes, check without overwriting:

```powershell
python ../docs/reliability-evidence/task66_sampling_diagnostic.py <pinned-cache> ../docs/reliability-evidence/artifacts/task66-sampling-diagnostic-2026-10-07/report.json --check
```

Exact recreation passed in main and bounded read-only AI review. The
[related JUnit record](related.xml) contains 20 passes, zero failures/errors/skips
and 4.350 JUnit seconds (4.39 wall seconds). It covers the new diagnostic,
Task12 historical ambiguity and the pinned pair audit. Ruff lint/formatting pass
for 253 source/test/evidence files. The [verification record](verification.json)
binds these scopes and exact bytes. No new full-suite run is claimed: the engine
implementation is unchanged, and these are selected diagnostic checks.

plan.json: 14,644 bytes, SHA-256
`46e88a0be7a91f17151f214a1d5992c221105c8eae44d00e15b62541dec93c0e`.

report.json: 40,858 bytes, SHA-256
`d1f41d14ab593759192d2ec7ada7e77cdd8fb94465de932215c08fa258e43362`.

related.xml: 3,100 bytes, SHA-256
`77bda1e8feea25c9721f7b6feca2059b833ccbeb16bb101ed071d7a8a88e59b5`.

verification.json: 12,840 bytes, SHA-256
`3875195c452e6c3c83d8ea300d28506e2cf38eb8659636f68b4e3d061fbee587`.

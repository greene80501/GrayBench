# First complete protected graph reference scan

The protocol4 baseline at 3ed07d2 completed all 286 planned offline cases. Its
append-only event chain verifies, with no pending invocation. Eight external-service
tasks per suite were explicitly excluded, matching the historical offline selection.

| Suite | Pass | Unsupported | Infrastructure error | Total |
|---|---:|---:|---:|---:|
| Normal | 80 | 62 | 1 | 143 |
| Hard | 80 | 62 | 1 | 143 |

Against the preserved f131336 v3 baseline, each suite has 35 transitions from pass
to unsupported and six from unsupported to pass. These are compatibility regressions
and improvements to investigate individually; the stricter graph transport does not
justify declaring the smaller supported cohort sufficient. Neither protocol's counts
are model accuracy or proof that the private tests are correct.

The [machine-readable summary](GrayBench-v4-reference-summary-3ed07d2.json) records
all results, changed tasks, unresolved diagnostics, source hashes and exclusions.
The raw log is [preserved here](GrayBench-v4-protected-full-reference.jsonl), SHA256
`4453d6feafb17a980c311b9991c9e2ccdb601fdeb78297b693388568f888421e`.
The chain head is
`9e4573ca1b1822a8270ebd2159a217e90cfb34b25c2a8df243be7e0d323b649a`.

Gaps include retained and packed operation families, transpiled circuit metadata,
DAGs, figures, jobs, custom passes and SDK objects, external array ownership and
transport size. Task82 still relies on an upstream cross-process file assumption;
its separate semantic recipe was not substituted into this exact-upstream scan.

Runtime sources were checked before and after every invocation. Barrier development
took place in a separate worktree while this run continued. The baseline therefore
precedes that fix and the unexpected-bridge-exception hardening; later targeted
replays must not be added to these counts to manufacture a new aggregate.

Required follow-up: resolve or explicitly review every changed task against native
behavior, finish the remaining graph interfaces, repeat complete admission after
those changes, and complete independent oracle/provider/reproducibility review.
No model generation API was used for this calibration.

# Native test-exception conditions

The pinned Qiskit HumanEval tests can raise after an incorrect candidate has
returned. For example, task 4 passes the candidate's `None` return to Qiskit's
`Operator` constructor, which raises `QiskitError`. The
[286-case screen](native-null-return-screen.md) found 62 such completed
test-phase exceptions per 143-task offline suite. The historical native worker
classified non-assertion exceptions without a candidate stack frame as
`infrastructure_error`, leaving a model run unscored.

New native development cohorts may explicitly choose
`test_exception_is_failure_v1` with `native-plan --exception-policy`. Under this
condition, any exception escaping the pinned test is a failed answer unless
its traceback contains a candidate frame, in which case the outcome remains
`candidate_error`. Both are scorable wrong-answer outcomes. An error while
executing the public prefix, a Docker launch failure, timeout, output limit,
missing completion, or unverifiable result file still uses the corresponding
non-pass outcome outside this test-exception rule. The unchanged
`conservative_unattributed_v1` condition remains the default and continues to
block a score on unattributed non-assertion test exceptions.

The cohort, protocol, worker payload and judge manifest bind the selected
condition. Native plan/create output and ledger summaries name it, and paired
comparisons reject a policy mismatch. Historical cohort and protocol JSON omit
the new optional field, preserving their serialized identities; their old
source-bound evidence is retained. The `native-reference-scan` command accepts
the same option for canonical calibration and records it in its header and
printed summary. A new output path is required for every scan.

This condition is a scoring convention, not proof that the test is correct or
that an exception was caused by the candidate. The native candidate and test
share a Python process, and task 63 already has a demonstrated false pass.
Reference passes and simple wrong-answer controls alone cannot admit a task.
Both policies remain development-only; publication still requires reviewed
task contracts, controls, stability checks, and independent reproduction.

## Pinned calibration and control

The following complete chains used engine source digest
`8d4d2ee6a6959e6f0c8bda91cea0120eaeb183e56fb31b34d7bc0b405c2358aa`
and Docker image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
Eight external-service tasks per suite were excluded before freezing the
143-task offline cohorts. Each chain's source manifest matched the local
engine at inspection.

| Chain | Planned | Outcome | SHA-256 | Chain head |
| --- | ---: | --- | --- | --- |
| [Normal canonical](native-reference-normal-scored-2026-09-27.jsonl) | 143 | 143 pass | `83b61a5a526889e2da2e0a77edba05f70d70e0e9c462d7a7806943795af315e5` | `fb60b8bf069e270211e119d3f4567df5f5e0b8866e89475d7fc2768801d0b4a3` |
| [Hard canonical](native-reference-hard-scored-2026-09-27.jsonl) | 143 | 143 pass | `fe7f0bc8f2ed2424ee11c5b7e2a5cd4373914d86a9d2030c58f47776855dacdc` | `7e19ba9219db889ca932c92411cb5c87eb3f8bc38d1a6e95e63279691655d7b1` |
| [Both-suite null-return control](native-scored-null-return-screen-2026-09-27.jsonl) | 286 | 286 fail | `c9037ff4542d678696a8f14675a90446ce52c8cd5bb4a8234971fe1606ddbb7b` | `120c6e864dcafe3f5d181ad882ec647d2917a5383407ec6413246e94de719ec5` |

The explicit-policy canonical cohort digests are
`54fc373c65502f105646091a25b5e42674ec3faddf4243a220500512fee22b8c`
for normal and
`9f67e142bcf2757b0635d73c8ba58b8fe3367ff24fe7b13e41d86fceeba4ccca`
for hard. The control's [probe source](native_scored_null_return_screen.py)
has SHA-256
`95a045e6abb43b7d86010b355460618a23cf0b22f97b7bf2f177168d0be1a520`.

Compared task by task with the [conservative null-return screen](native-null-return-screen.md),
162 outcomes stayed `fail` and 124 changed from `infrastructure_error` to
`fail`, 62 in each suite. All 124 were completed test-phase exceptions in the
older chain; the new chain has no infrastructure error or pass. The paired
normal and hard outcomes agree for every offline task. This validates this
policy's handling of the selected wrong-answer control, but does not prove
that every task rejects other wrong answers. Task 63's fixed-string false pass
remains a concrete counterexample to such a claim.

## Current-source paired literal screen

The [October 6 explicit-policy run](artifacts/native-literal-mutants-scored-2026-10-06/README.md) repeats two literal answers on every offline normal and hard task under current engine source `0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924`. Its 572 cases pair exactly with the [conservative run](artifacts/native-literal-mutants-2026-10-06-v2/README.md): 366 failures and four passes are unchanged, while 202 completed test-phase exceptions become failures. Four `[]` false passes on tasks 110 and 139 persist. The verifier now checks the logged non-pass outcome against the captured worker status as well as the event chain and artifact bytes; exact source copies preserve both historical probe identities. This strengthens the local evidence, but does not resolve native oracle adequacy or authorize a model score.

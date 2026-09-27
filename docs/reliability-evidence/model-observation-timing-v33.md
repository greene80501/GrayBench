# Protocol 3.3: bounded model-observation timing

Protocol 3.3 extends the attempt-bound pre/post observations of [protocol
3.2](attempt-model-observation-v32.md). The manifest freezes a maximum
pre-observation age and maximum delivery-receipt-to-post delay. New development setups
default to 30 and 120 seconds; `campaign-plan --protocol-version 3.3` accepts
explicit `--max-pre-observation-age` and `--max-post-observation-delay` values.
Both bounds must be positive finite seconds at most 3600. A paired comparison
requires matching timing bounds. Existing 3.1/3.2 manifests omit this field,
preserving their identity and evidence semantics.

The ledger checks the exact latest pre-observation against the timestamp used
for attempt start and checks again after dispatch intent commits. A stale or
future pre-observation stops dispatch. If the commit itself exhausts the bound,
the attempt remains unresolved and an append-only timing-abort event records
the cause. A post-observation is bound after durable delivery even when late,
retaining the answer and the failure evidence. After that binding commits, a
separate append-only check records the post-commit time. A crash before this
check leaves the run unscored. The ledger reports pre/start, start/finish,
finish/post, finish/post-commit, and post/post-commit gaps and any negative or
over-bound gap.
Such a run stops
further generation and judgment and has a
`model_observation_timing_violation` score blocker. Missing post evidence,
missing post-commit confirmation, and unfinished delivery retain separate
statuses. Direct ledger calls have
the same gates as the campaign runner.

The [offline tests](../../engine/tests/test_model_observation_timing.py) cover
default and custom policy freezing, paired-policy mismatch, timely transport,
stale/future pre-dispatch checks, slow dispatch/post commits, a backward
generation clock, slow delivery persistence, late/backwards post observations,
crash before post confirmation, retry pairing, retained generation, scoring
blockage, and ledger integrity. The tests use an Ollama
`httpx.MockTransport` fixture and make no billable provider calls.

The finish timestamp is sampled when `finish_attempt` receives the transport
result, before serialization and persistence, so those delays count against
the post bound. The post-observation timestamp is sampled after metadata
retrieval and before commit; the second check samples just after that commit.
Thus the evidence binds host sample times, not exact database-commit or
network-wire times. These gaps use the host's UTC
wall clock. They are neither independent clock
attestation nor proof of unchanged provider weights, routing, or effective
settings during the request. An operator controlling the host clock or ledger
can manipulate observations absent external provenance controls. The score is
a development result until task admission, judge adequacy, provider
calibration, external anchoring, and independent reproduction are complete.

On source-manifest digest
`edccbe9ed26ec8832aa3e9012f2bd488cf3528547802841e4d4b8ddf3350c00c`,
the full local Python 3.12 offline suite passed with 912 passed, 219 skipped,
zero failures and zero errors. Its external JUnit record is
`work/outputs/GrayBench-v4-protocol33-offline-final.xml`, SHA-256
`0e41b23911915748511a5160c99da3afd0868b239ab7ce4358bd47b05a562d73`.
With the immutable local evaluator image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
and parser image
`sha256:731a7ed19488145b2a0ba0d7efbb4528d13cc6466ca3ba114254bb5ab4782ae9`,
the same 1,131-case suite finished with 1,130 passed, one skipped, zero
failures and zero errors in 624.39 seconds. The one skipped case is the cached
Hamiltonian definition control, which requires a separate experimental
registered-storage image. The external protected JUnit record is
`work/outputs/GrayBench-v4-protocol33-protected-final.xml`, SHA-256
`560a7169103f8bc32a8dd6a31c744a9dc12e9bbb5bd84f269a96b42004a232ee`.
Ruff check and format checks passed, and a final independent read-only review
found no remaining Critical or Important timing issue. These integration tests
do not substitute for task admission or live provider calibration.

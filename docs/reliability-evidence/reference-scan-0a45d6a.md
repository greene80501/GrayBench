# Complete offline reference scan at 0a45d6a

All 143 offline reference tasks in each suite were attempted from an isolated checkout.
Every engine source hash was verified against commit 0a45d6a before execution, and every
recorded judge-manifest file hash was subsequently checked against that frozen source manifest.
The evidence file hash and full unresolved-task list are in the adjacent JSON summary.

| Suite | Pass | Unsupported | Infrastructure error | Candidate error | Timeout |
|---|---:|---:|---:|---:|---:|
| Normal | 92 | 48 | 1 | 1 | 1 |
| Hard | 92 | 48 | 1 | 1 | 1 |

These are reference-interface outcomes, not LLM scores or oracle certification. Tasks
43, 97, 98, 122, 129, 133, 134 and 146 were explicitly excluded as service-dependent.
The historical c7ade58 scan remains unchanged. This scan also excludes later quantum-value
and persistent-control fixes, whose targeted evidence is recorded separately.

Task 82 needs file transport; task 100 hit the candidate output limit; task 109 exposed
per-call lifecycle overhead. Later task-109 replays passed after replacing CLI launches with
persistent Docker control. Task-100 transport/resource classification still requires review:
its reference returns a Solovay-Kitaev decomposed circuit, so a wire-size limitation must not
automatically be treated as a model-quality failure.

## Durable reference tooling

The new reference-scan/reference-inspect commands replace the fragile scratch output pattern.
Each run exclusively creates a JSONL output, fsyncs a header and a started event before executing
a reference, then appends chained result/completion events. Engine source changes during the
scan stop it. Explicit offline selection and excluded task digests are recorded. Inspection
checks ordering, identities and truncation with bounded per-event reads; interrupted invocations
remain pending. Existing outputs cannot be overwritten or silently resumed.

The chain detects accidental modification; it is not an external signature or protection
against a host owner who rewrites the whole file. Independent artifact anchoring and a reviewed
recovery/adjudication workflow remain release requirements.

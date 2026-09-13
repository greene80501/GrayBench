# Reproduced specification and oracle findings

These findings are development evidence, not model scores or a completed task review.
The original upstream track must retain its pinned tests; corrected contracts and stronger
oracles belong to a separately versioned track with the same public requirements for all models.

| Task | Evidence | Required resolution |
| --- | --- | --- |
| 9 | Twelve parameterized RX gates plus a barrier pass the current EfficientSU2 oracle despite having no entangling gates. This is distinct from the historical issue already fixed upstream. | Check the requested ansatz semantics using explicit parameter correspondence and equivalent positive implementations. Parameter count alone is insufficient. |
| 14 | The public prompt requires 100 shots, but the test accepts the two-item list `["00", "11"]`. | Enforce the declared shot count and document what aspects of execution can actually be verified from the returned data. |
| 20 | An empty circuit with the correct layout passes upstream. The independent GHZ behavioral check rejects it, a product superposition, an incomplete Bell state and a relative-phase mutant while accepting two equivalent positive constructions. | Complete the task review; the behavioral check does not prove which pass-manager algorithm was used. |
| 32 | Bell-state expectations for II, XX, YY, ZZ are +1, +1, -1, +1. The reference uses an undisclosed -1 coefficient for YY and the test requires the resulting signed sum 4. The prompt asks for the expectation values without specifying that weighting. | Resolve the public output contract before strengthening the test. Do not quietly score an undisclosed signed observable as the only valid interpretation. |
| 35 | The reference chooses variational parameters using a hidden RNG seed 1234 and a uniform distribution. The prompt specifies neither those parameter values nor that sampling rule, but the test requires an expectation near 0.33. | Declare the parameter preparation in a corrected public contract or revise the observable behavior being tested. Do not silently supply the reference values only to selected models. |

The concrete local observations and public prompts are retained in
[additional oracle evidence](reliability-evidence/GrayBench-v3-additional-oracle-findings.json).
The protected reference-interface scan is summarized separately in
[interface evidence](reliability-evidence/GrayBench-v3-reference-interface-summary.json).
Every task's full specification, positive-alternative and mutation review remains pending.

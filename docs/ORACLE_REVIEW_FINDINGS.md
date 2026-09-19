# Reproduced specification and oracle findings

These findings are development evidence, not model scores or a completed task review.
The original upstream track must retain its pinned tests; corrected contracts and stronger
oracles belong to a separately versioned track with the same public requirements for all models.

| Task | Evidence | Required resolution |
| --- | --- | --- |
| 3 | Both upstream suites accept a blank Matplotlib Figure alongside the circuit. They also accept measuring only qubit 0; the prompt does not clearly specify measurement coverage. | Validate that the drawing represents the returned circuit, and clarify measurement coverage before adding stricter requirements. Faithful Figure transport alone does not repair this oracle. |
| 26 | Both suites accept a Bell pair on qubits 1 and 2, although the prompt specifies 0 and 1. They reject the requested unmeasured pair because they require an undisclosed measurement and depth 3. | Specify measurement semantics and verify Bell-pair placement/coherence. Avoid incidental reference gate-count/depth requirements. |
| 9 | Twelve parameterized RX gates plus a barrier pass the current EfficientSU2 oracle despite having no entangling gates. This is distinct from the historical issue already fixed upstream. | Check the requested ansatz semantics using explicit parameter correspondence and equivalent positive implementations. Parameter count alone is insufficient. |
| 14 | The public prompt requires 100 shots, but the test accepts the two-item list `["00", "11"]`. | Enforce the declared shot count and document what aspects of execution can actually be verified from the returned data. |
| 20 | An empty circuit with the correct layout passes upstream. The independent GHZ behavioral check rejects it, a product superposition, an incomplete Bell state and a relative-phase mutant while accepting two equivalent positive constructions. | Complete the task review; the behavioral check does not prove which pass-manager algorithm was used. |
| 32 | Bell-state expectations for II, XX, YY, ZZ are +1, +1, -1, +1. The reference uses an undisclosed -1 coefficient for YY and the test requires the resulting signed sum 4. The prompt asks for the expectation values without specifying that weighting. | Resolve the public output contract before strengthening the test. Do not quietly score an undisclosed signed observable as the only valid interpretation. |
| 141 | Both upstream suites accept ten zero SparsePauliOp objects because their anticommutators are zero multiples of identity. Zero is not a Pauli operator. | Check the permitted Pauli family as well as the anticommutator relation; disclose phase conventions without imposing the reference's random construction. See [protected probe](reliability-evidence/sparse-operators.md). |
| 35 | The reference chooses variational parameters using a hidden RNG seed 1234 and a uniform distribution. The prompt specifies neither those parameter values nor that sampling rule, but the test requires an expectation near 0.33. | Declare the parameter preparation in a corrected public contract or revise the observable behavior being tested. Do not silently supply the reference values only to selected models. |

The concrete local observations and public prompts are retained in
[additional oracle evidence](reliability-evidence/GrayBench-v3-additional-oracle-findings.json).
The protected reference-interface scan is summarized separately in
[interface evidence](reliability-evidence/GrayBench-v3-reference-interface-summary.json).
Every task's full specification, positive-alternative and mutation review remains pending.

The [task 3/26 review](reliability-evidence/task3-26-review.md) includes exact pinned-test
results for 14 trusted authored fixtures in a separate diagnostic container. The latest
[complete offline reference scan](reliability-evidence/reference-scan-8399f3d.md) records
103 passes, 39 unsupported interfaces and one file-boundary error per suite. Reference
compatibility is not task admission or proof of oracle adequacy.

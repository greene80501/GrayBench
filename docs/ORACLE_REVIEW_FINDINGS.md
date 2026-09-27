# Reproduced specification and oracle findings

These findings are development evidence, not model scores or a completed task review.
The original upstream track must retain its pinned tests; corrected contracts and stronger
oracles belong to a separately versioned track with the same public requirements for all models.

| Task | Evidence | Required resolution |
| --- | --- | --- |
| 63 | Both protected suites accept constant `"1"`. For the actual ideal circuit, only 2 of 32 independent uniform receiver bases produce that key; the private seed affects the judge, not the candidate. | Publish a coherent randomness/output contract and test varied behavior without sharing private RNG state. See [protected constants and exhaustive basis witnesses](reliability-evidence/task63-oracle-review.md). |
| 109 | Both suites accept a fixed plus state and a parameter that changes only global phase through all 1,000 checks. The test checks polar angle but never equatorial coverage. | Specify the parameter/resource contract and test physical state variation; parameter count alone is insufficient. See [exact-test native diagnostic](reliability-evidence/task109-oracle-review.md). |
| 116 / 120 | Both normal and hard upstream tests accept fixed circuits that ignore all function arguments and match only the single tested example. | Exercise varied Pauli strings, times, widths and diagonal phases against independent semantic expectations. See [protected evidence](reliability-evidence/numeric-gate-transport.md). Hamiltonian/diagonal transport support does not repair these tests. |
| 114 | Both exact upstream tests accept physical qubit 8 instead of the requested isolated qubit 7, because they check only node count. | Verify physical-qubit identities as well as directed edges. Graph transport also needs mutation/cache fidelity; see [diagnostic evidence](reliability-evidence/task114-graph-review.md). |
| 113 | Both suites accept a constant plain dictionary ignoring the input, while the PropertySet reference was initially unsupported by the bridge. The transport follow-up now passes the reference but leaves the false accept intact. | Preserve the required return type and test varied inputs including cases where removing barriers changes depth; see [protected evidence](reliability-evidence/task113-contract-review.md). Do not confuse transport support with oracle correctness. |
| 37 | Both suites accept fabricated PrimitiveResult data with a non-bit string and no algorithm execution. The canonical answer returns 00000 for input 1111. | Specify output/register semantics and validate recovered strings and result consistency; see [protected evidence](reliability-evidence/primitive-containers.md). Returned data alone cannot prove backend execution. |
| 46 | Both suites accept a fixed three-qubit identity LinearFunction that ignores the requested width and seed. | Check parameter/seed behavior and the declared generation method; see [protected replay](reliability-evidence/linear-functions.md). |
| 86 | Both suites accept identity blocks with the expected block counts but no requested CX-chain behavior. | Check circuit semantics and declared block constraints together; do not impose the reference's undisclosed extra H gate. |
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

Task 141 now has a separately versioned [public-contract revision](reliability-evidence/task141-pauli-revision.md).
Protected replays accept both references and valid phase/matrix alternatives while
rejecting the zero-operator counterexample. It remains release-ineligible and does
not replace historical upstream scores.

The [task 3/26 review](reliability-evidence/task3-26-review.md) includes exact pinned-test
results for 14 trusted authored fixtures in a separate diagnostic container. The latest
[complete graph offline reference scan](reliability-evidence/reference-scan-38db7fa.md) records
113 passes, 28 unsupported interfaces, one failure and one file-boundary error per suite. Reference
compatibility is not task admission or proof of oracle adequacy.

A later [complete source-guarded replay](reliability-evidence/reference-scan-77f29ff.md)
records nine additional unsupported-to-pass references per suite. Its observed
hard task-63 pass is unstable: 20 fresh canonical replays per suite passed once
in normal and never in hard. Both task-63 variants remain release-ineligible;
the new aggregate is interface evidence, not a fair model score.

A separately named [explicit receiver-bases revision](reliability-evidence/task63-explicit-bases-revision.md)
now supplies the missing basis input in the public contract and uses a new
protected checker. Its 14 authored control runs matched their predeclared
outcomes across normal and hard, but it remains a development recipe; the
upstream task and its historical results are unchanged.

Tasks 116 and 120 now have separately selected [behavioral revisions](reliability-evidence/gate-semantics-revisions.md).
They retain historical upstream results and make the changed scoring contract
public before generation. Finite semantic checks do not certify internal methods.


## Object-identity fidelity blocker

Six [native-versus-protected identity probes](reliability-evidence/alias-boundary.md)
reproduce one false acceptance and five false rejections caused by value-only
transport. This affects identity-sensitive behavior even without a visible value
mutation. The opt-in [protected graph protocol](reliability-evidence/protected-graph-development.md)
now repairs those six fixtures. Historical protocol 3 retains these defects and
is not an automatic fallback. Full SDK coverage and calibration remain unfinished;
release-ineligible status remains necessary. Passing these controls does not
certify every interface or the adequacy of the upstream tests.

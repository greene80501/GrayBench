# Protected graph batch design

## Purpose and evidence

Task 63's explicit-bases recipe needs stronger oracle coverage without timing out correct implementations. A pinned-image probe of 584 individual graph exchanges timed out two correct implementations after 256 exchanges at the 120-second candidate-active limit. In the same pinned image, the 584 BB84 computations took 0.339 seconds for the simulator reference and 0.198 seconds for a statevector alternative when run without the bridge. A synthetic one-exchange graph batch passed both implementations with 1.890 and 1.718 seconds of candidate-active time. That synthetic wrapper was supplied with candidate code and is only feasibility evidence; it must not be used in a benchmark.

The intended benchmark result is a new, separately named development condition. A model continues to implement `bb84_circuit_generate_key(senders_basis, circuit, receivers_basis)` one case at a time. The benchmark owns the batch loop and never gives the candidate expected results or test assertions. The existing nine-case `qhe63-explicit-bases-v1` condition remains frozen.

## Transport contract

Protocol 4 gains an opt-in, manifest-bound `positional-batch-v1` mode. The trusted test process calls `candidate.batch(cases)` with a nonempty tuple of at most 1024 positional-argument tuples. It snapshots those arguments as one graph call. The host relays the graph without reconstructing candidate objects. The candidate worker validates the batch envelope and calls the model's ordinary entry point once per case, in order, inside the isolated candidate container. It returns a tuple of results through the existing graph codec. A candidate exception stops at the first affected case and follows the existing exception path. No test expectation or verdict enters the candidate container.

This mode is **not** claimed to be semantically identical to 584 independent graph exchanges: all inputs are reconstructed before the first model call, and mutations and retained state can differ. The condition identity therefore records the batch mode, transport, byte/node limits, image, timeouts, and exact task/test digests. An ordinary protocol-4 setup cannot silently use batch mode. The trusted test, not the model source, decides when to invoke it. Candidate code may inspect its own process, but cannot inspect trusted expectations held in the separate judge container.

The host, trusted process, and worker must reject undeclared batch calls and malformed envelopes. The worker must reject zero cases, more than 1024 cases, non-tuples, and invalid argument shapes before running any candidate call. The trusted process must reject a returned value with the wrong tuple length or per-case type as a test failure for task 63. Wire and graph limits remain enforced by the existing codec; limit failures remain `unsupported` or infrastructure outcomes, not incorrect answers.

## Task-63 condition

`qhe63-explicit-bases-v2` keeps the v1 public signature and ideal independent BB84 domain. Its trusted test covers all 584 sender-bit, sender-basis, and receiver-basis combinations at widths 1–3, plus four larger or equivalent-preparation cases from v1. Expected sifted keys are derived in the trusted process from authored bits and matching bases, never from a candidate implementation. It makes one bounded batch call and checks exactly 588 string results in order. The prompt is identical to v1; the task and judge identities differ because the private test and protocol do.

The new condition stays `release_eligible: false` until authored wrong/correct controls, independent oracle and transport review, resource calibration on more correct styles, and admission bindings are complete. It is value/graph-development evidence, not native Qiskit equivalence or a model score.

## Verification

Tests must show that the opt-in is required, old single-call behavior still works, the worker executes the original model entry point for each case without candidate-supplied wrapper code, malformed batches are rejected before execution, exceptions retain their classification, and a wrong per-case result fails. Under the pinned image, both correct task-63 styles must pass normal and hard; authored wrong styles must fail; the candidate exception must remain `candidate_error`. Record exact source, image, task, judge, control, and output hashes before proposing admission.

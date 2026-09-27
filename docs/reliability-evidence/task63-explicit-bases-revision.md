# Task 63: explicit receiver bases development recipe

The pinned upstream task asks for a BB84 key but hides the receiver-basis draw
inside the reference. Its judge seeds a different process and demands one exact
key, so a correct independent implementation can fail while a constant answer
can pass. The [original task-63 audit](task63-oracle-review.md) and later
[40-repeat reference replay](reference-scan-77f29ff.md) remain historical
upstream evidence. This change does not alter either pinned dataset or its
recorded results.

`qhe63-explicit-bases-v1` is a separately selected development recipe for normal
and hard task 63. It gives the function a third public argument,
`receivers_basis`, and states the full observable domain before generation:
equal-length binary basis sequences, an unmeasured circuit of independent ideal
BB84 states, and a string of bits retained where bases match in ascending
qubit-index order. No receiver bases are drawn inside the answer. The normal
completion prompt contains only the `QuantumCircuit` type import; unused
inherited RNG, Sampler and simulator imports are removed. The hard prompt uses
the same argument order and semantic contract. Neither prompt contains a
reference, fixture or judge outcome. The checker does not prescribe a simulator,
transpiler, register name or circuit-mutation policy.

The protected checker creates a fresh circuit for each of nine cases, with
varied bit patterns, widths, basis agreements and disagreements, no matching
bases, order-sensitive keys and one equivalent `H-Z-H` preparation for an X.
Expected sifted bits are computed directly from the authored classical bit and
basis fixtures. Two cases use identical bases but different prepared bits, so a
basis-only answer cannot pass. The candidate is called through graph protocol 4
with the pinned Python 3.12/Qiskit image; protocol 3 and delta transport are
rejected. A result must be an exact Python string. Candidate faults and
transport/infrastructure outcomes remain distinct from incorrect keys.

The [source-guarded raw replay](GrayBench-v4-task63-explicit-bases-controls.jsonl)
contains 14 predeclared protected runs: corrected simulator reference and an
independent statevector implementation both passed in both formats; fixed-one,
basis-only, no-sifting and reversed-order mutants failed in both; a deliberate
candidate exception remained `candidate_error` in both. No model API was called.
The [probe](task63_explicit_bases_probe.py) reserves an output before execution
and does not overwrite existing evidence. The [verifier](verify_task63_explicit_bases.py)
checks the complete hash chain, each expected outcome, original and revised task
identities, public request identity, image, graph protocol, engine source and
probe hash. A verifier regression test rewrites one declared case digest and
recomputes a valid chain; the verifier rejects the altered case identity. The
pinned normal and hard source task digests are
`2ba17e13c1e97e2ad2b96ed3de9589a31f28f3a75553d1b2651e34abb5715ce1`
and `c456c4772f149f8f88a28f473c4b3b7278490b820847a5dc4327246ec5d8c4af`.
The final raw file SHA-256 is
`b1c47a1e99d331833e9d331b66b36db1e4ea6fad812d8c77740df116bfb4c56a`;
its chain head is
`641a441140dad8437c9b1c41c194a4d81bff1850f85ef815bbe0d8cd93974b55`.
The earlier e92ad14 artifact was valid only in the isolated checkout: its
`graph_limits.py` working bytes had CRLF line endings, while the same Git blob
checked out with LF in the PR worktree. The source guard correctly rejected
cross-checkout verification. All 14 controls were rerun from the LF checkout,
with the same predeclared outcomes, and this final artifact verifies there.
The prior artifact remains recoverable in Git history; its results are not
combined with the new ledger.

From `engine/`, after obtaining the pinned dataset and immutable image:

```powershell
uv run --extra dataset python ../docs/reliability-evidence/task63_explicit_bases_probe.py NEW_OUTPUT.jsonl --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --docker 'C:/Program Files/Docker/Docker/resources/bin/docker.exe'
uv run --extra dataset python ../docs/reliability-evidence/verify_task63_explicit_bases.py NEW_OUTPUT.jsonl
```

The development recipe is still `release_eligible: false`. Nine authored cases
cannot prove universal behavior, an algorithm's internal method, transport
coverage outside this input domain or independent quantum correctness. Noisy,
measured, entangled and malformed inputs are outside v1. Separate domain review,
larger mutation/alternative audit, reference stability and uniform resource
calibration remain necessary before a new score could be admitted. Its results
must never be merged into an upstream or published 101/151-task percentage.

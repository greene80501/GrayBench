# Task63 BB84 hidden randomness and constant-answer acceptance

Both pinned upstream suites accept a candidate that ignores the basis and circuit
and returns the constant string `"1"`. The companion `"0"` control fails in both.
These are four protected protocol4 executions with one recorded call each, not
native unisolated candidate scoring. The complete event chain, judge manifest
digests and unchanged engine source were verified.

The public task asks for BB84 key generation from sender bases and a circuit. It
does not expose the private test's NumPy seed. The reference samples receiver
bases with NumPy; the private test seeds NumPy in the judge and requires one exact
result. A seed in a separate judge process does not seed candidate randomness.

For the actual fixture, sender bases are `[1,0,0,1,1]` and bits are `[0,0,0,1,1]`.
The probe enumerates all 32 possible receiver bases. For each, it applies the
receiver basis rotations to the actual ideal circuit, computes a native Qiskit
Statevector distribution, and verifies that the matching-basis bits produce the
analytically sifted key with probability one (tolerance 1e-12). It respects native
bitstring ordering explicitly. Only two receiver choices produce `"1"`.

Thus **conditional on independent uniform receiver bases and this ideal fixture**,
the demanded string occurs with probability 2/32 = 6.25%. This is an exhaustive
calculation, not a measured failure rate of a model, provider or canonical sample
campaign. The seeded legacy receiver vector `[0,1,1,1,0]` does yield `"1"`, which
explains the assertion when candidate and judge share RNG state.

IBM's BB84 explanation describes random receiver bases and retaining results
where sender and receiver bases agree. That supports the distinction between
protocol behavior and the undisclosed shared RNG assumption; it does not endorse
any proposed benchmark repair.
[IBM Quantum Learning](https://quantum.cloud.ibm.com/learning/en/modules/computer-science/quantum-key-distribution)
(accessed 2026-09-23).

## Evidence and limits

- `GrayBench-task63-constant-oracle.jsonl`: SHA256
  `67c0db59275559d05cde4e2cd873140e95409f46f354253b05c2f2974e3c566d`;
  chain `535c0aaa42ea075c8fca055d3b7772ac492a4ef1702dcb36708fa9e026af441e`.
- `GrayBench-task63-basis-enumeration.json`: all 32 basis/matching-index/key
  witnesses, probabilities, seed witness, task digests, probe hash and versions.
- `task63_oracle_probe.py`: protected fixtures and independent analytic/native
  cross-check, run from engine/ with fresh output arguments and the documented
  workspace-relative dataset cache. No IBM hardware, accounts or model API calls.

This does not change upstream scoring, copy private RNG state into candidate
containers or reroll a failed reference. The historical reference failures remain.
A corrected track must first publish its randomness and return contract. Supplying
receiver bases explicitly would make a different deterministic task; exposing a
seed still requires specifying RNG scope and algorithm and can constrain valid
implementations. Merely accepting a plausible subsequence is insufficient because
an implementation could fabricate it without the required behavior. Any revision
needs independent positive implementations, counterexamples and stated limits on
what observable outputs can prove. No revised oracle is admitted by this audit.

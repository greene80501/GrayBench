# BB84 explicit receiver bases, development recipe

The approved reliability overhaul requires a fair replacement for Qiskit
HumanEval task 63's hidden random assertion. The pinned upstream track stays
byte-for-byte intact and keeps its historical judgments. A new, explicitly
selected `qhe63-explicit-bases-v1` recipe changes the public task and judge
together; its results cannot be combined with upstream percentages.

## Public task and observable contract

The normal completion prompt keeps the function-completion format and the
`QuantumCircuit` type import, removing inherited unused simulator, Sampler and
random-number imports that could mislead the solver. It changes the signature to
`bb84_circuit_generate_key(senders_basis, circuit, receivers_basis)`. The hard
standalone prompt declares the same three arguments. Both disclose that the
equal-length binary basis sequences and an unmeasured `n`-qubit circuit are
provided for `n >= 1`. The circuit prepares independent ideal BB84 states:
each sender bit is encoded in the sender's Z (`0`) or X (`1`) basis. The function
returns a Python string of measured bits for positions where the sender and
receiver bases match, in ascending qubit-index order. Nonmatching positions are
discarded. The returned sifted bits are deterministic for these ideal inputs;
the function chooses no receiver bases. The public contract requires no
particular simulator, transpiler, circuit mutation behavior or register name.
Malformed bases, previously measured/noisy circuits and external-service
behavior are outside this v1 domain.

This gives every model the same information required to solve the declared
task without publishing exact test cases, solutions, solver hints or
feedback. It does not claim to test key distribution under noise or a full
cryptographic BB84 protocol.

## Protected check

The trusted side constructs fresh circuits and expected sifted strings from
independent classical bit/basis fixtures, then calls the candidate once per
case through graph protocol 4. Cases vary width, bits, sender and receiver
bases, all-match/no-match/mixed sifting, order and one equivalent gate
preparation. At least one pair shares basis inputs but uses different prepared
bits. Expected values are computed from bit positions, never from the
candidate's random state or the canonical implementation.

Accept a string exactly equal to the expected bits. Include positive controls
using both a simulator-based implementation and an independent statevector
implementation. Reject controls that return a fixed string, ignore the
circuit, omit basis sifting or reverse the key. Candidate errors, unsupported
graph values, timeouts and infrastructure failures stay separate outcomes.
The finite suite is a falsification screen, not proof of universal correctness.

## Identity and safety

The recipe freezes revised public prompt, private check, corrected reference,
source, immutable Python 3.12 image, graph protocol/limits and task identity in
the existing campaign and judge manifests. Revision happens before model request
hashes are computed and is reconstructed on resume. No private fixture, expected
string or corrected reference enters a provider request. An explicit selection
cannot fall back to legacy protocol 3 or upstream scoring. Run/replay evidence
retains original and revised task digests separately.

Release eligibility stays false pending independent quantum/domain review,
larger mutation/positive-control audit, reference stability and uniform
resource calibration. The original task-63 40-repeat failure record remains
unaltered. IBM's [BB84 learning module](https://quantum.cloud.ibm.com/learning/en/modules/computer-science/quantum-key-distribution)
supports the same-basis sifting rule, but does not certify this revised oracle.

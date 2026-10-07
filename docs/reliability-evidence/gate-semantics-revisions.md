# Gate semantics revisions for tasks 116 and 120

The original task116/120 tests each exercise a single input and accept fixed
answers that ignore the supplied arguments. The original upstream track and its
preserved counterexamples remain unchanged. Two explicit development recipes
add varied behavioral checks:

- `qhe116-evolution-semantics-v1`: sixteen Pauli/time pairs, one to four qubits,
  covering I/X/Y/Z, tensor order, identity strings, zero and negative times.
- `qhe120-diagonal-semantics-v1`: twelve diagonals, one to four qubits,
  covering real and complex phases, unequal entries and varying widths.

Both revise the public request before provider preparation and protocol hashing.
Unrevised tasks, another family and the wrong entry point are rejected. Setup
serialization/resume reconstructs the same public revision and protected tests.
Original upstream generations cannot simply be relabeled as revised-track runs.

## Public semantics and fairness

These are explicitly behavioral tracks: the original requests name particular
Qiskit construction/synthesis methods, but returned circuits cannot demonstrate
which procedure actually ran. The appended contract therefore explicitly scores
returned-circuit semantics and allows equivalent implementations. It does not
claim to test adherence to the original named routine. That changes the scoring
contract and is a reason not to compare these scores directly to upstream ones.

Evolution uses the exact `exp(-i*time*P)` matrix, including global phase. This
matches the original test's direct matrix comparison. Diagonal outputs may differ
by an overall unit-modulus phase, preserving the original `Operator.equiv`
allowance. Both publish absolute tolerance 1e-10 and relative tolerance zero.
The diagonal contract forbids input mutation; the current mutation bridge marks
such attempts unsupported rather than silently accepting or scoring them as wrong.
Valid inputs, expected width and phase conventions are declared uniformly to all
models. Exact test inputs, expected matrices and reference code are not supplied
in provider requests.

The evolution oracle constructs Pauli matrices from explicit 2x2 arrays and
Kronecker products, then applies `cos(t) I - i sin(t) P`, using `P^2 = I`.
It does not call PauliEvolutionGate, MatrixExponential or HamiltonianGate to obtain
expected answers. The diagonal oracle directly constructs `numpy.diag(input)`;
it does not derive expected values through DiagonalGate. Output extraction still
uses the pinned Qiskit Operator implementation; this is not fully independent
runtime verification.

The [IBM PauliEvolutionGate reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.PauliEvolutionGate)
defines the time evolution and the rotation factor of two. The
[IBM Diagonal reference](https://eu-de.quantum.cloud.ibm.com/docs/en/api/qiskit/1.1/qiskit.circuit.library.Diagonal)
describes the diagonal entries; its documented version is not the runtime.
Local execution is pinned to Qiskit 2.4.2.

## Limits

These finite authored cases are development evidence, not hidden holdout tests,
exhaustive verification or independent task admission. Candidate representations
still require separately supported transport; equivalent circuits with unsupported
instructions remain unscored. Release eligibility stays false. The revisions do
not establish model scores, provider comparability or procedural compliance.

## Validation

The final Docker-enabled suite passed **423 tests**, with zero failures, errors
or skips, in 180.07 seconds. Local report:
`outputs/GrayBench-v3-gate-semantics-tests.xml`. Eighteen new focused tests cover
protected positive/negative answers, pre-generation contract binding, saved-plan
reconstruction, and wrong-family/entry rejection.

A separate code-review agent reported no actionable findings and passed four
non-Docker checks; the parent ran the fourteen protected cases. This is code review,
not independent scientific certification. Ruff lint and all 82 formatting checks
passed. No model API generations were used.

[Protected normal/hard replay](GrayBench-v3-gate-semantics-evidence.jsonl) records
32 completed source-bound cases, no pending attempt, and all expected outcomes:
ten reference/alternative results pass and 22 counterexamples fail. This includes
both actual canonical references in both suites, a Hamiltonian alternative and a
diagonal alternative with an allowed global phase. Incorrect examples cover fixed
answers, evolution sign/factor/order/phase, conjugated/reversed diagonals, wrong
width, magnitude scaling and non-finite matrices.

Evidence SHA-256:
`ea10384530b4183103bacb2724ec3d82cadf028fbcd20d93985f5610099c9115`.
Original and revised task records, authored answers, pinned image, transcripts and
actual worktree source hashes are retained. CRLF worktree hashes may differ from
Git-normalized blobs; this is not claimed as an exact Git-byte replay.

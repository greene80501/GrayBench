# Hamiltonian and diagonal instruction transport

The fixed numeric_gate_v1 record retains the exact HamiltonianGate or DiagonalGate
class, name, label, parameters and cached definition. It does not replace a gate
with its unitary matrix or synthesize a circuit during transport. Numeric array
bytes preserve dtype and endianness; Hamiltonian evolution time supports the
existing bounded symbolic representation. Custom definitions retain their circuit
name and metadata. Absent caches stay absent.

The decoder selects one of two fixed classes, initializes Gate state, and assigns
explicit decoded parameters. This deliberately bypasses the public constructor's
physical validation and coercion: a submitted non-Hermitian matrix or nonunitary
diagonal must not be repaired or rejected as an incorrect answer by transport.
Correctness remains the oracle's responsibility. Payloads cannot specify arbitrary
imports, class constructors or attribute names.

Hamiltonian matrices are limited to seven qubits; diagonals to nine. Extra object
state, subclasses, malformed dimensions and unknown fields are unsupported.
Existing scalar finiteness, symbolic complexity, recursive definition and output
limits apply. Hamiltonian and unitary matrices share a 512 KiB cumulative
decoded matrix budget across nested instruction definitions. Alias identity is not admitted. A cached DiagonalGate definition
containing UCRZ remains unsupported because UCRZ has no faithful codec yet; an
uncached DiagonalGate can be transferred and evaluated by Qiskit normally.

Installed Qiskit 2.4.2 source was inspected for both constructors and definitions.
The [IBM circuit library reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/circuit_library)
identifies these as diagonal transformation and Hamiltonian evolution gates;
that documentation is not substituted for the pinned runtime source.

Tasks 116 and 120 retain their original upstream tests. Both tests exercise only
one input (X at time 1, and diagonal [1, i, -1, -i], respectively). This is a
coverage limitation for public functions accepting arbitrary Pauli/time or
diagonal arguments. Protected input-ignoring controls are recorded separately
from passing canonical references. Neither establishes task admission or a
certified model score.

## Protected evidence and review

[Source-bound protected replay](GrayBench-v3-numeric-gate-evidence.jsonl) contains
12 completed cases with no pending attempt: four canonical references pass,
four empty-circuit controls fail, and four input-ignoring counterexamples pass
(two tasks, normal and hard). SHA-256:
`309294c0993fdbd623ae1b55dac7742567392974aaa693ca0b9768b76ed9110d`.
Actual worktree byte hashes, pinned image and full task/completion identities are
retained. Worktree CRLF hashes need not equal Git's normalized source blobs.
No model API generations were used.

The independent code review found that Hamiltonian matrices bypassed the existing
circuit matrix budget. Four regression cases first reproduced the missing rejection
and then passed after unifying the budget across Hamiltonian/unitary operations,
including nested generic definitions. Fourteen focused tests pass. The initial
full suite passed 401 tests before this review fix; final validation is recorded
below. Cached UCRZ and the broader alias/object-state boundary remain unadmitted.

Final Docker-enabled regression suite: **405 passed**, zero failures, errors or
skips (154.16 seconds). Report: local artifact
`outputs/GrayBench-v3-numeric-gate-final-tests.xml`. Ruff lint and all 80 format
checks passed. The focused tests include four aggregate-budget regressions;
the protected replay used the final source after that fix.

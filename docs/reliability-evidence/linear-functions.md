# LinearFunction transport and task review

The fixed instruction registry now supports exact Qiskit 2.4.2 `LinearFunction`
objects, standalone or embedded in circuits. The data-only record includes the
boolean matrix, name, label, original circuit and any already cached definition.
Original and cached circuits use the existing bounded circuit codec. The encoder
does not call lazy synthesis. The decoder constructs only the fixed Qiskit class;
it does not load arbitrary classes, execute serialized code, or deserialize pickle.

Qiskit's [LinearFunction API](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.circuit.library.LinearFunction)
exposes both the matrix and the original circuit. The installed pinned source
confirms they are separate parameters and that definition generation is lazy.
The codec retains these independently, including a deliberately different cached
definition or a matrix changed after construction. Reconstructing solely from
the original circuit would silently change those candidate values.

Singular boolean matrices are preserved with `validate_input=False`, matching
Qiskit's constructor default: physical validity belongs to the oracle, not a
transport repair step. Matrix dimensions, boolean dtype and fixed record fields
are checked. Existing numeric-byte, circuit-operation and nesting bounds apply;
cyclic nested definitions remain unsupported. Subclasses, arbitrary added
attributes and shared-object alias semantics are not admitted by this codec.

Tests exercise standalone and embedded forms, wire order, names/labels, original
circuit and cached metadata, divergent matrix/circuit contents, lazy definition
absence, singular matrices, malformed matrix shape, unexpected constructor
fields and cyclic definitions. None of these establish oracle adequacy or full
task admission.

## Protected reference and counterexample replay

Both task 46 and task 86 canonical solutions pass in normal and hard suites.
All four authored counterexamples also pass upstream: task 46 returns a fixed
three-qubit identity matrix while ignoring both arguments; task 86 returns one
identity LinearFunction block and two smaller identity blocks without building
or collecting the requested CX chain. These are false accepts of deliberately
nonconforming implementations, not model results. Task 46 needs parameter/seed
behavior checks; task 86 needs circuit behavior and declared block constraints
checked together. Requiring the reference's extra Hadamard gate would need a
public-contract justification and must not be silently imposed.

The complete source-guarded log is `GrayBench-v3-linear-function-evidence.jsonl`,
SHA-256 `1d47caba588fe45cfed8c5861e59d2111cbdb2cf444bd54c8efc4d062ad160af`.
It includes original task records, authored code, expected contract outcomes,
actual upstream outcomes, runtime identities and protected call transcripts.
Actual worktree source bytes are retained; Windows line endings can differ from
Git blobs. This targeted replay does not replace the prior complete scan.

Final validation: 347 tests passed with Docker enabled, no errors, failures or
skips, in 132.75 seconds. Ruff lint/format checks and credential-value scanning
passed. No model API generation calls were made. All task admission remains pending.

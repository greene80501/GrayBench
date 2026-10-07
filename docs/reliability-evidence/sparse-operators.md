# Scalar and sparse Pauli operator exchange

The protected bridge now supports exact ScalarOp and SparsePauliOp objects with
fixed constructors and bounded data records. Task 107 returns a ScalarOp. Task 141
requires a SparsePauliOp input and a list of SparsePauliOp outputs; both directions
now use the same representation.

Scalar records preserve coefficient value/type, input and output subsystem
factorization, and bound qargs. Numeric scalar support follows the existing Python
and NumPy value codecs; arbitrary Number subclasses are not coerced to floats.
Sparse records preserve the Boolean X/Z arrays, public Pauli phases, coefficient
array, term order, duplicate terms, explicit zero terms, empty operators, subsystem
factorization and bound qargs. Numeric complex coefficients retain their bytes,
including non-finite values. Object coefficient arrays support the existing bounded
symbolic parameter format and share one parameter-identity context on decode.

No operator is simplified, normalized, converted to a dense matrix, or replaced by
a reference answer during transport. Reconstructing the Pauli list uses the fixed
symplectic constructor and retains phases separately from coefficients. The sparse
constructor is instructed not to fold those phases into coefficients again.

The codec validates schemas, array shapes/dtypes, coefficient counts, Pauli width,
phases and subsystem dimensions. A scalar coefficient cannot embed another operator
constructor. The candidate and both judge container file allowlists include the new
operator codec; no private tests, credentials or arbitrary constructors are added to
the candidate environment.

Limits remain explicit: existing numeric-array and subsystem-dimension bounds apply;
symbolic coefficient arrays have a 16,384-element cap and the existing symbolic-program
limits. Unsupported coefficient objects/dtypes and bound qargs types are not silently
converted. This is a value representation, not serialization of arbitrary monkeypatches,
private caches, object aliases, subclass behavior or global numerical-tolerance settings.
Alias-aware input mutation and broader scientific codec capacity classification still
require work. The tasks remain ineligible for publication pending their full reviews.

## Reference evidence

The four pinned reference cases (normal/hard task107 and task141) pass through the
isolated upstream judge. The source-guarded append-only log is
`GrayBench-v3-sparse-operator-reference.jsonl`, SHA-256
`efb2a706d3d310cf0a6b329c60649feca96125b98bd2c3922c4a316153786d0b`.
The inspection reports complete with no pending invocation. Task141's reference
uses random Paulis; one successful invocation per suite is compatibility evidence,
not a stochastic reliability estimate. The older complete 103-pass-per-suite scan
remains unchanged; targeted improvements are not represented as a new full scan.

Tests cover coefficient types, reshaped/bound operators, phase and matrix equivalence,
duplicate/zero terms, symbolic binding with shared parameter identities, non-finite
coefficient bytes, empty operators and malformed records. No model generation calls
were made for this interface calibration.


Final validation: 323 tests passed with Docker enabled, zero failures/errors/skips,
in 105.30 seconds. Ruff lint/format and the credential-value scan passed. The
reference and counterexample event headers/results are also retained in
`GrayBench-v3-sparse-operator-evidence.json`; their full append-only logs remain in outputs.

## Task 141 oracle defect exposed by interface support

Both pinned upstream suites accept a list of ten zero SparsePauliOp objects. The
zero operator is not a Pauli operator, but its anticommutator with every input is
zero times the identity, satisfying the only operator-property check in the test.
A strengthened contract must validate membership in the permitted Pauli family as
well as the requested anticommutator relation, and state its allowed phase convention.
It must not force the reference's random construction or require unique results
unless those requirements are actually disclosed in the prompt.

The protected counterexample completed normally for both suites in
`GrayBench-v3-task141-zero-sparse-probe.jsonl`, SHA-256
`4da3592fa5582b0d3b1adb8e3af3913e1aa7df67131577fb437823f9541e9e16`.
The candidate received only its public task/input; it had no access to test code.
This is local authored counterexample evidence, not an independent task review.

An earlier diagnostic used zero ScalarOp values instead. Both tests raised a Qiskit
mixed-operator exception and remained unscored infrastructure_error, rather than
passing. That inconclusive probe is retained unchanged in
`GrayBench-v3-task141-zero-operator-probe.jsonl`, SHA-256
`e22cc9981481f90d2455afc794cd1558f9edb2374729541c66b04633cde63461`.
It is not represented as a false accept. Classification of arbitrary upstream-test
exceptions still requires task-specific admission work.

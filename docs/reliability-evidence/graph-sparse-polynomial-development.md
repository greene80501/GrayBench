# Sparse and polynomial graph components

This increment extends the standalone graph with CNOTDihedral, SpecialPolynomial,
PauliList and numeric SparsePauliOp components. It is not connected to production
candidate calls. The [production identity defects](alias-boundary.md) remain
unresolved there, and overall release eligibility remains false.

CNOTDihedral retains its actual polynomial object, linear and shift storage,
subsystem shape, bound qargs and instance dictionary. SpecialPolynomial retains
its dictionary, coefficient arrays and integer constant type. Shared polynomials
stay shared. Integer-list shift forms remain lists, including their NumPy scalar
elements. Coefficients are not reduced modulo eight and invalid affine values
are not repaired. This follows the stored representation described in IBM's
[CNOTDihedral documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.quantum_info.CNOTDihedral),
with identity behavior verified against the pinned SDK.

PauliList retains its stored X/Z and internal phase arrays. The public `phase`
property is derived from that internal representation; reconstructing through
labels or public phase values would risk changing storage and aliases. Numeric
SparsePauliOp retains its PauliList, coefficient array, shape and qargs. It does
not combine duplicate terms, reorder rows, absorb phases again, or repair values.
Equal-valued component replacements remain distinct, and detached earlier arrays
remain synchronized through held references.

Fixed schemas verify polynomial combination counts, widths, array shapes and
dtypes, Pauli row counts and coefficient lengths before updates. Mirrored instance
dictionaries are checked against those schemas. The existing matrix budget also
charges the distinct underlying owners of affine and symplectic matrices.
PauliList has a native `(rows, qubits)` shape, which is now included when validating
DataBin leading dimensions.

## Verification

All 21 new tests first failed at the missing graph capability, then passed with
the implementation. They cover component sharing, native numeric forms, invalid
values, duplicate sparse terms, raw phases, detached children and malformed late
updates that must leave existing objects untouched.

The full Docker-enabled suite passed **571 tests** in 190.75 seconds on 2026-09-19,
without failures, errors or skips. Local JUnit artifact:
`outputs/GrayBench-v4-sparse-polynomial-full-tests.xml`. Lint and formatting checks
were also run.

The expanded trusted standalone probe passed **15 checks** in pinned image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`,
using Python 3.12.14, NumPy 2.2.4 and Qiskit 2.4.2. Eight explicit graph dependency
modules and the fixture were mounted read-only, with no network, an unprivileged
user and bounded resources. This is not a protected v4 oracle/candidate replay.
[Raw result](GrayBench-v4-sparse-polynomial-linux-probe.json) SHA-256:
`8afb6043d97b06bff2dbd6dc1e17c02bab5bb3412269a367060e0ca20c8ae1e0`.
Hashes identify the actual mounted source bytes; Windows CRLF bytes may differ
from Git-normalized LF blobs. Earlier evidence remains unchanged.

## Remaining work

Symbolic SparsePauliOp coefficients still require a safe object-reference array
and symbolic-node representation. Raw NumPy object-pointer bytes must never cross
the boundary. Native inspection also showed that SparsePauliOp can create distinct
ParameterExpression objects from repeated parameter inputs; restoration must
preserve actual stored identities rather than invent constructor aliases.

Parameter/vector relationships, stable expression replay, array geometry updates,
circuit components, production RPC integration and protected admission remain
unfinished. No model API generations or certified model scores were produced.

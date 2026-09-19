# CNOTDihedral transport

The numeric wire supports exact Qiskit CNOTDihedral objects without converting
them to circuits or matrices. It preserves the affine matrix, shift and phase
polynomial constant, linear, quadratic and cubic coefficients. Numeric array
bytes retain dtype and endianness. Integer constants retain Python versus NumPy
scalar types. Invalid numeric coefficients and singular matrices are preserved
for the oracle rather than silently reduced or repaired.

In the pinned Qiskit 2.4.2 environment, a directly constructed element has an array
shift; composition can produce a list of NumPy integers. The codec preserves both
forms. The SDK equality method raises AttributeError even when comparing a
composed list-shift object to itself in the inspected case. Tests therefore
compare its explicit fields and matrices instead of changing the representation
to make that SDK method succeed.

The decoder uses a fixed CNOTDihedral constructor and bounded numeric state. No
class names, imports or arbitrary attributes are supplied by the payload. Qubit
counts are bounded to 1–64 before allocation; matrix/vector/polynomial shapes and
schema keys are checked. Existing per-array and output byte limits apply. Bound
subsystems, custom subclasses/attributes, inconsistent polynomial metadata and
unsupported constant/list element types remain unsupported. Alias identity is
not admitted. These are declared transport limits, not a correctness judgment.

[IBM's API reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.quantum_info.CNOTDihedral)
describes the affine/phase-polynomial representation and circuit synthesis API.
The implementation was additionally checked against the installed 2.4.2 source;
the documentation version is not presented as the runtime version.

Tasks 105 and 106 still use their original pinned upstream checks. Reference
compatibility and simple negative controls cannot establish complete oracle
adequacy, general behavioral equivalence, or independent task admission.

## Review and protected checks

Both pinned normal/hard references for tasks 105 and 106 pass through the
protected upstream bridge. Returning the two-qubit identity fails all four checks.
These eight authored cases calibrate the interface, not model accuracy.

The scoped reviewer identified an inconsistency between the object's private
qubit count and operator shape that would otherwise be silently corrected during
decoding. A regression test reproduced it before the encoder was changed to
reject that state. The codec preserves representable numeric errors but does not
claim to preserve contradictory structural metadata.

Final source-bound replay: [GrayBench-v3-dihedral-normalized-evidence.jsonl](GrayBench-v3-dihedral-normalized-evidence.jsonl),
SHA-256 `e7ebd95d66778a13c46d864d3e0891baf1a69b1ea07f9cb4e0ebe9b50a49414d`.
All eight expected outcomes matched. Actual worktree bytes are recorded and may
differ from Git LF blobs. The [initial replay](GrayBench-v3-dihedral-evidence.jsonl)
predates the metadata rejection fix and is retained as historical evidence, not
substituted for final validation.

The full Docker suite passed 391 tests in 155.11 seconds, with no failures, errors
or skips. After line-ending normalization, all seven focused tests and all eight
protected replay cases passed again; lint and formatting checks passed. Tests
cover representation, composition, invalid numeric preservation, metadata and
shape rejection, array byte fidelity and scalar types. No model API was called.

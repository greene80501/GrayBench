# Symbolic transport calibration

The replacement engine's circuit_v3 format preserves Parameter UUIDs and ParameterVectorElement
identities and numeric ordering. A bounded fixed-operation replay interpreter reconstructs
supported expressions; it does not evaluate strings or deserialize QPY/pickle. Vector allocation,
expression depth/steps, exponent magnitude and numeric intermediates are bounded. NumPy scalar
gate parameters preserve their dtype. Private Qiskit 2.4 interfaces require compatibility checks
before any runtime upgrade.

Targeted local reference replays for normal and hard tasks 7, 8, 9, 99 and 111 passed. Task 127
initially remained unsupported because it returned NumPy scalar parameters; a subsequent fix and
separate replay passed both cases. The original full reference scan at c7ade58 is unchanged.
No updated full-suite pass count is inferred from these targeted checks.

Validation: 144 local tests passed, including 32 Docker tests against the pinned immutable image.
The checks cover expression binding, vector ordering, equivalent parameterized circuit operators,
UUID conflicts, malformed operations, bounded allocations, and unsupported error classification.
The user-facing replay JSON and JUnit artifacts retain the detailed local evidence.

Worker protocol 3 identifies decoding, execution and encoding phases. Decoding/encoding failures
remain unscored pending adjudication, since unsupported representations can be valid answers.
These diagnostics are untrusted: a forged encoding error can prevent completion but cannot
establish correctness. Existing ledger tests prohibit aggregate accuracy for unsupported samples.

Remaining limitations include substitution/gradient expression replay, complex symbolic literals,
custom/control-flow instructions, circuit metadata/labels, aliases/mutations and richer SDK objects.
All task review cards remain unreviewed; reference compatibility alone does not certify an oracle.

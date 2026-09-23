# Converted instruction metadata

The pinned Qiskit 2.4.2 `circuit_to_gate` converter creates a plain Gate and adds
`condition = None`. Its `circuit_to_instruction` counterpart adds `_condition = None`
to a plain Instruction. The graph codec previously required exactly the base
instance fields, rejecting these ordinary converted objects. This also blocked
controlled gates whose base gate came from a circuit conversion.

The fixed codec now includes these two explicitly named optional fields for their
respective exact classes. It preserves absent fields, present null values, and
supported referenced values. It retains the actual instance dictionary and
aliases through field addition, deletion and detached references. It does not
invent a missing field, reinterpret it as a new control-flow operation, or admit
arbitrary attributes or subclasses. Standard singleton and control-flow field
rules are unchanged.

State fields must agree with the referenced instance dictionary, including exact
reference tokens. Graph validation still checks every referenced node before
commit. Optional metadata is reconstructed as raw instance state, without a
constructor that could normalize it or copy its children.

## Verification

Four new local tests first failed at `Extra or missing instruction fields require
another codec`. After the change, the focused instruction/controlled suite passes
46 tests, including protected snapshot and delta cases. Those protected tests
verify dictionary/definition identity, bidirectional metadata mutation and a
negative control whose missing field must remain missing and fail the assertion.
Unknown fields and divergent dictionary/state descriptions remain rejected.

A separate read-only review found no blocking correctness or security issue. It
did not run tests or Docker. It suggested further receiver-side malformed-field
controls; these are distinct from the already tested sender rejection and
state/dictionary mismatch. The complete Docker-enabled suite passed **972 tests
in 416.01 seconds**, with zero failures, errors or skips; its JUnit record is
`GrayBench-v4-converted-instruction-tests.xml`. Ruff lint and formatting checks
pass for all 140 engine/test files. These checks validate the implemented scope,
not full benchmark admission.

## Exact reference comparison

All twelve selected normal/hard cases were unsupported before this change.
Tasks 90, 91, 112, 119 and 125 now pass in both suites. Task 120 remains unsupported:
it gets past converter metadata and reaches a retained Python operation that
needs another component codec. That unresolved outcome is preserved.

Both complete event chains, task selections, task identities, canonical completion
hashes, extraction hashes, public task digests and judge manifest digests were
verified. The after-scan engine source exactly matches the tested checkout.
The only semantic source change is `graph_instruction.py`. Exact source bytes
also differ in `graph_limits.py`, `graph_quantum_circuit.py` and `graph_wire.py`
because the baseline checkout retains CRLF and the updated checkout has LF.
Byte comparison after newline normalization confirms those three files have
identical content. Original manifests and byte hashes are retained, not normalized
or relabeled as identical experiments.

| Artifact | SHA256 |
|---|---|
| GrayBench-v4-converted-instructions-before.jsonl | aa5bf01f1d487681cc3d85c293e96a8e48d6a43849199a24668bdaef331c993b |
| GrayBench-v4-converted-instructions-after.jsonl | ccffffa3b53750ef7b71386cc7f103d57eb43a095df69ccb07b9dd779c2620e2 |

Before chain: `d46baa62497aeda08cb311238d49041d8e582e1883fdf25a5f749b529006cb6e`.
After chain: `fa5294941075fa668f8eedadd9e6c05346c1772976cb0c4ca684bd438276b2c8`.
`GrayBench-v4-converted-instructions-summary.json` preserves all transitions.
`converted_instruction_reference.py` reproduces the selected exact tests from
`engine/` with an explicitly supplied new output path and its documented workspace
cache path. The raw logs bind the pinned image and unchanged default limits.
Probe SHA256: `ce28bf22f555be35bd1d98ac29b61390f1025fbeaad20a33bb45010098098e21`.

These scans ran while other diagnostic/regression work was active. Their timings
are not an isolated performance comparison or a basis for production budgets.
They are interface calibration, not model scores or oracle admission. They do
not replace the complete historical 286-case aggregate. The original task 120
oracle defects also remain independent of transport support.

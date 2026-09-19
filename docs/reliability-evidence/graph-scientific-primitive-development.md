# Scientific and primitive graph components

This development increment extends the standalone [container and numeric graph](graph-core-development.md).
It is not integrated into the production worker. The [six production identity
defects](alias-boundary.md) remain unresolved there, and release eligibility remains false.

## Implemented representations

| Objects | Preserved components |
| --- | --- |
| Statevector, DensityMatrix, Operator, Choi | Existing numeric arrays, shared OpShape objects, subsystem tuples, bound qargs and exact instance dictionaries. |
| ScalarOp | Numeric coefficient type/identity, OpShape and bound qargs; no dense expansion. |
| Clifford, StabilizerState | Tableau arrays, nested Clifford instances, OpShape and instance dictionaries. Invalid symplectic values are not repaired. |
| BitArray | Packed uint8 array, bit count, stored shape tuple and instance dictionary. |
| DataBin | Stored data dictionary, attribute dictionary and shape tuple as separate references, including repeated fields and cycles. |
| PrimitiveResult, PubResult, SamplerPubResult | Actual stored result list, shared DataBin, empty/nonempty metadata dictionaries and applicable instance dictionaries. |

Restoration does not call constructors that copy arrays/lists, replace empty
metadata, normalize physical values or canonicalize dimensions. It allocates fixed
SDK shells and attaches already validated components. An instance dictionary is
itself a graph node: passing `vars(value)` must refer to the same dictionary at the
receiver, and two objects sharing one dictionary must retain that relation.

Scientific/BitArray/PrimitiveResult dictionaries permit only the exact fixed SDK
fields. Their component tokens must match the dictionary tokens, including the
distinction between integer 1 and boolean True. No payload-selected attribute or
constructor is invoked. DataBin's dynamic field names follow its restricted-name
rules, with dunder names rejected; its stored mapping and attribute mapping are
validated separately and never silently made equal.

This distinction matters: native `data.a = replacement` can change DataBin's
attribute while leaving `data["a"]`/its stored mapping unchanged. The graph preserves
that divergence. It also preserves the observable difference between implicit
qubit dimensions and an explicit dimension tuple in OpShape.

Array shapes, subsystem counts, packed-bit dimensions, DataBin leading dimensions,
component classes, reserved fields and mirrored dictionary state are validated
before applying any updates. Aggregate matrix storage is charged once per distinct
owning buffer referenced by matrix/tableau wrappers, in addition to the general
array budget. Abstract OpShape dimensions do not allocate dense matrices: this
permits a 20-qubit Clifford tableau without inventing a dense representation.

## Evidence and scope

The scientific tests cover two wrappers sharing an array, distinct equal
replacements, detached earlier arrays, shared instance dictionaries, consistent
dimension updates, bound qargs, invalid physical/symplectic values, malformed late
updates and independent matrix-budget enforcement. Primitive tests cover shared
metadata, retained lists, DataBin mapping/attribute divergence, cycles, packed-bit
shapes and rejection of reserved-field attacks before metadata changes.

Native pinned-Qiskit source inspection established the constructor and storage
behavior. Public APIs are described in IBM's [Statevector documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.quantum_info.Statevector)
and [Operator documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.quantum_info.Operator).
The tests verify the stronger identity claims on Qiskit 2.4.2; the documentation
links alone do not establish those claims.

Remaining graph capability entries are explicit:

| Existing tree-supported family or form | Current graph status |
| --- | --- |
| SparsePauliOp, CNOTDihedral | Unsupported; Pauli/polynomial component graphs still required. |
| Parameter, ParameterExpression, parameter-vector elements, symbolic coefficients | Unsupported; shared symbolic-node representation still required. |
| QuantumCircuit, standalone Instruction/Gate and supported standard/custom gate families | Unsupported; Task 3 must preserve component ownership and caches. |
| Array geometry changes, external buffers, dtype metadata and non-admitted numeric forms | Unsupported as recorded in the numeric increment. |
| Seeded scientific RNG objects and extra scientific instance attributes | Unsupported; never silently discarded or replaced with judge-global state. |

No graph payload falls back to the old tree codec. Task 2 remains in progress;
scientific/primitive coverage here does not imply circuit support, completed
protected judging or a score comparable to an official benchmark.

## Verification result

The final Docker-enabled suite passed **550 tests** in 181.34 seconds on 2026-09-19,
with no skips, failures or errors. This includes 30 scientific and 16 primitive
graph tests. Lint and formatting checks passed. Local JUnit artifact:
`outputs/GrayBench-v4-scientific-primitive-final-tests.xml`.

The expanded trusted fixture passed **13 checks** in the pinned image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
(Python 3.12.14, NumPy 2.2.4, Qiskit 2.4.2). It used eight explicitly mounted graph
dependency modules and the trusted probe, with no network, a read-only filesystem,
an unprivileged user and bounded resources. This is not protected candidate/oracle
admission evidence. [Final raw result](GrayBench-v4-scientific-primitive-validated-linux-probe.json)
SHA-256: `fe169414d7e593abb87c37c3c3d41b12d1dcfd859080eacc2f2cc812b94a8e32`.

A late regression test caught an oversized integer escaping the instance-dictionary
validator as a generic JSON ValueError. The corrected path raises WireError and a
subsequent valid snapshot succeeds in the same arena. The earlier 549-test result
and [12-check probe](GrayBench-v4-scientific-primitive-linux-probe.json) are preserved
as intermediate evidence (probe SHA-256
`46c6f1b67ac0d0e0cf2da7567e4aa897912b52df4266dc75bae6c87c89739a9e`).
They precede this error-classification correction.

Source and probe hashes were checked against actual mounted working-tree bytes.
Windows CRLF hashes may differ from Git-normalized LF blob hashes. Earlier evidence
files remain unchanged. No model API generations were performed.

# Task 139 protected value revision: implemented, pending independent review

The pinned normal and hard task 139 tests accept `[]`: they loop over returned Schmidt terms without requiring any term or reconstructing the input. The [current-source literal control](artifacts/native-literal-mutants-2026-10-06-v2/README.md) reproduces that pass in both suites. The original native tests remain byte-for-byte pinned. This design defines a **separate value task** to test the requested mathematical result without claiming native `Statevector` identity, Qiskit algorithm use, or equivalence to a native score.

Two tempting revisions are unsuitable as headline fixes. Replacing the pinned native test would erase exact upstream comparability and retain same-process test inspection. Comparing returned tuples to one Qiskit `schmidt_decomposition` result would reject valid phase choices, term orderings, and orthonormal rotations within degenerate Schmidt subspaces. The proposed protected value condition instead checks the mathematical definition by reconstruction.

## Public call and result

The callable receives `state` as exactly 16 `[real, imaginary]` pairs in Qiskit little-endian four-qubit statevector order and `qargs_B` as a nonempty proper list of distinct indices in `0..3`. Inputs are normalized finite states. The result is a nonempty list of at most `min(2**len(B), 2**(4-len(B)))` objects with exactly these fields:

```json
{"weight": 1.0, "a": [[1, 0], [0, 0], [0, 0], [0, 0]], "b": [[1, 0], [0, 0], [0, 0], [0, 0]]}
```

Here `weight` is a positive real Schmidt coefficient. The example represents `|0000>` when `qargs_B=[0,1]`. `a` and `b` contain complex amplitude pairs and must have lengths `2**(4-len(B))` and `2**len(B)`. The `a` index uses the complement of `qargs_B` in ascending qubit order. The `b` index uses **sorted** `qargs_B`, regardless of the list's input order. Both use little-endian indexing within their subsystem. This matches an observed Qiskit 2.4.2 `schmidt_decomposition` convention for unordered `qargs_B`; the public revision must state it so no model has to guess it.

## Trusted value condition

The host-side oracle parses finite numeric pairs and checks, with frozen absolute tolerance `1e-8` and zero relative tolerance:

1. At least one and no more than the dimension-limited number of terms; every coefficient is strictly positive and at most one. No arbitrary minimum nonzero Schmidt coefficient is imposed.
2. Each subsystem vector has unit norm. The `a` vectors are mutually orthogonal, and the `b` vectors are mutually orthogonal.
3. The squared coefficients sum to one.
4. Reconstruct all 16 amplitudes as `sum(weight * a[a_index] * b[b_index])`. The reconstructed state matches the input after one global-phase alignment, with maximum per-amplitude error at most `1e-8`.

Term order, local phases, global phase, and degenerate Schmidt-basis rotations are accepted if these invariants hold. The oracle derives indices and reconstruction in plain Python rather than comparing to a Qiskit return object. A shape-valid but semantically wrong result is a failure; malformed output is a candidate error. A timeout or worker failure remains distinct and unscored.

## Frozen case and control plan

The planned call domain is all 40 ordered nonempty proper partitions of four qubits crossed with six public state families: `|0000>`, `|1011>`, GHZ+, two crossing Bell pairs, a nontrivial complex product state, and a deterministic generic complex state with full 2+2 Schmidt rank. This gives 240 exact calls. The ordered-partition duplication tests that the published sorted-vector convention is honored. Cases are deterministic, finite, normalized, and source-bound to both pinned suite records.

Positive controls include an independent NumPy matrix SVD, Qiskit's decomposition adapted to the JSON representation, a common global phase, reordered terms, and a rotated basis in a degenerate subspace. Negative controls include `[]`, a fixed `|0000>` answer, an omitted nonzero term, nonorthogonal subsystem vectors, a misnormalized weight, and an incorrect subsystem order. The empty list is a `candidate_error` because it violates the declared nonempty result shape; the other wrong but shape-valid answers are `fail`. Controls are frozen before Docker execution and run in both suites under the same pinned image. A verifier checks their declared outcomes, candidate source digests, judge manifests, and engine source.

Even after local controls pass, this revision remains development-only. Independent reviewers still need to assess the public clause, tolerance, case adequacy, valid alternatives, wrong mutants, and the known native finding. Its scores cannot be combined with the native track or published until the task-admission gate is satisfied.

The [current-source local control log](artifacts/task139-protected-controls-2026-10-06-v2/README.md) records 22/22 expected outcomes across both suites. This is authored evidence, not independent certification.

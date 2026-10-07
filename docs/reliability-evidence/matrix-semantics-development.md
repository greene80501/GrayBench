# Source-bound matrix conditions for tasks 116, 120 and 125

Three explicitly selected development conditions qualify returned matrix actions under uniformly revised public contracts. The original pinned tasks, original tests, legacy task-116/120 semantics recipes and previous artifacts remain unchanged. These conditions do not establish exact native semantics, internal construction methods or publication eligibility.

| Condition | Expected action | Phase policy | Authored input corpus |
| --- | --- | --- | --- |
| `qhe116-evolution-graph-v2` | `cos(t) I - i sin(t) P` for an unsigned Pauli tensor `P` | Global phase is retained | 16 Pauli/time pairs, widths 1–4 |
| `qhe120-diagonal-graph-v2` | The diagonal given by the input values | Overall unit-modulus phase is allowed | 12 diagonals, widths 1–4 |
| `qhe125-gate-action-graph-v1` | A Gate equivalent to each original input circuit | Overall unit-modulus phase is allowed | 18 circuit actions, widths 1–4 |

All three publicly specify absolute tolerance `1e-10` and zero relative tolerance. Valid input domains are stated independently of these finite cases; the corpora are not exhaustive domain verification. Circuit/gate widths must match. Gate subclasses and equivalent representations are allowed for task 125. Evolution and diagonal construction procedures are explicitly not scored. Task 125 covers numeric unitary inputs without classical bits or unbound parameters, rather than assuming a symbolic/nonunitary conversion policy that the original tests never established. Inputs may be modified, but results must describe their original values. The task-120 v2 mutation policy differs explicitly from the legacy v1 prohibition.

The old task-125 checker checked only shape/type for its first returned gate, allowing an unrelated three-qubit action; its [original diagnostic](task125-gate-conversion-oracle-review.md) remains historical evidence. The new checker tests every return action. It builds expectations from literal local matrices, direct little-endian tensor embeddings and basis-index CX permutations. Cases include empty circuits, spectator wires, both CX orientations, complex local gates, nonzero phase, register insertion order, an explicitly supplied definition with permuted wires, and a parameter bound before dispatch. It freezes expected actions before allowing input mutation. Output extraction uses the pinned Qiskit `Operator` runtime and still needs independent runtime calibration.

Evolution/diagonal reuse the independent expectation formulas from the [legacy behavioral checks](gate-semantics-revisions.md): Pauli tensor arrays and the involution identity, and `numpy.diag` of original values. The new conditions reconstruct the exact six pinned source records before deriving a revision. Changed prompts, tests, references, formats, entries or family identities are rejected even if task IDs are reused. Only an exact original or exact revision is accepted. Normal and hard retain their respective completion/standalone formats; neither public request includes the authored controls or private test corpus.

Each condition freezes graph protocol 4, delta transport and individual calls, with structural depth 128 and 16 MiB default state/wire/output allowances. Arrays and matrices retain 512 KiB bounds, and nodes/edges retain 100,000 bounds. A different explicitly selected byte allowance changes judge/protocol identity; incompatible plans cannot be pooled. These are resource conditions, not a promise to transport every possible valid Python/SDK representation.

The [authored control runner](matrix_semantics_controls.py) predeclares manifests and complete rosters before isolated execution:

| Family | Trials across both formats | Expected passes | Expected failures |
| --- | --- | --- | --- |
| 116 | 18 | 6 | 12 |
| 120 | 24 | 10 | 14 |
| 125 | 32 | 10 | 22 |
| Total | 74 | 26 | 48 |

Correct alternatives include basis-change/parity-rotation Pauli evolution without an evolution synthesizer; Walsh phase expansion using only CX/RZ rather than a Diagonal gate; direct converters, Gate subclasses and equivalent nested definitions; and permitted input mutation. Wrong controls cover ignored inputs, sign/factor/tensor-order errors, incorrect first gate action, reversed wires, inverse/transposed/conjugated action, incorrect width/type, unbound output parameters, magnitude scaling and nonfinite matrices. These are authored alternatives, not independent reviewer attestations or model answers.

The [separate algorithm calibration](artifacts/matrix-alternative-calibration-2026-10-07/README.md) checked all 340 unsigned Pauli strings of widths 1–4 at three times (1,020 cases), plus 80 fresh random diagonals of widths 1–5. It retained global phase and observed maximum entry errors `6.66e-16` and `1.65e-15`, respectively. This calibrates authored algorithms independently of the production test inputs; it does not execute a model, graph worker or isolated container, and it does not exhaust continuous time or phase domains.

## Registered-native storage remains a qualification requirement

The canonical task-116 `MatrixExponential` path produces SciPy matrix-exponential storage backed by an external native capsule. The unadapted Windows dependency environment lacks the registered-storage extension and its graph transfer rejects that representation. This is the [already documented runtime limitation](native-graph-hamiltonian-development.md), not an incorrect canonical answer. The original `2fc74bd3…` image is also unadapted. A previously guarded experimental runtime supplied this capability, but its build dependencies were unpinned and it is not admitted. This change does not claim to qualify that runtime or silently copy away native ownership/alias relationships.

Canonical task-116 local semantic checks remain required and pass; its two complete graph tests are explicitly pending without observed registered-storage capability. The isolated control roster still requires the canonical answer to pass. It must not be removed, marked wrong, or treated as a passed transport control to accommodate an unqualified image. The full isolated test group uses an explicitly selected `GRAYBENCH_MATRIX_TEST_IMAGE`, distinct from the ordinary baseline-image setting. All three judge manifests remain `runtime_qualification: unqualified` and `release_eligible: false`.

From `engine/`, freeze a plan by selecting one of the condition names and its task in each suite:

```sh
uv run graybench campaign-plan model.json CACHE NEW_SETUP.json --name matrix-development --image sha256:QUALIFIED_IMAGE_DIGEST --evaluation-recipe qhe125-gate-action-graph-v1 --task normal/qiskitHumanEval/125 --task hard/qiskitHumanEval/125
```

Once Docker is healthy and a runtime is independently qualified, run each condition into its own new append-only log:

```sh
uv run python ../docs/reliability-evidence/matrix_semantics_controls.py --cache CACHE --image sha256:QUALIFIED_IMAGE_DIGEST --evaluation-recipe qhe125-gate-action-graph-v1 --output NEW_CONTROL_LOG.jsonl
```

Interrupted logs require adjudication, not replay under the same filename. No model API call is made by the runner. Local codec tests execute only authored trusted fixtures; model-generated answers must stay isolated. Worker execution, native-buffer/resource calibration, broader alternatives, independent requirement admission and matched external reproduction are still required before any headline score.

The [Qiskit 2.4 DiagonalGate documentation](https://eu-de.quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.circuit.library.DiagonalGate) defines the diagonal matrix entries. The [Qiskit 2.4 circuit conversion documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.circuit.QuantumCircuit) describes numeric unitary circuit-to-Gate conversion. Those references inform the public contracts; they do not validate these finite authored oracles.

## Verification

The focused current-source run passed 43 tests and skipped five: two canonical evolution graph checks without observed native-storage capability, and three isolated groups without an explicitly selected qualified image. The executed graph cases traverse 248 authored call pairs while retaining earlier nodes and checking accumulated wire traffic. Thirty local preparations across all five adapters contain the complete revised prompts and omit the exact private checker and original canonical answer; this bounded check does not establish provider receipt or a general disclosure guarantee. Actual CLI reservation tests confirm all 74 control cases and their source-bound judge manifests are recorded before execution.

Bounded read-only code review verified the six source identities, revision idempotence, original-value mutation expectations, manually constructed gate matrices, changed identities for distinct byte budgets and complete control-roster reservation. It found no blocking issue in that scope. It did not judge isolated runtime qualification, complete-domain coverage or independent task admission. The graph worker stages an explicit runtime-file allowlist, which excludes the new oracle and source-record modules.

The full main-checkout suite used locked Python 3.12.14/Qiskit 2.4.2 dependencies, pinned source cache, and no container test-image settings. It completed with **1,567 passed, 291 skipped, zero failures** in 430.07 seconds. The 60 warnings comprise 48 uses of the original deprecated `Diagonal` reference and 12 Windows temporary-directory cleanup warnings. Engine source digest: `4770bfec384cfe4f52a1fcd4cb832bed65f012a9234462f4dd25f531ab8cf90d`. Ruff lint and formatting passed for 228 files including both new evidence scripts. This is offline verification; Docker is unavailable and runtime/admission gates remain pending.

# Task 50: position-sensitive circuit editing

The pinned normal/hard test calls only position zero. An implementation that always removes the first gate passes it. The [original diagnostic](task50-110-oracle-review.md) also records the historical protocol-3 proxy rejecting the canonical input mutation. The pinned prompts, tests and existing native results remain unchanged.

`qhe50-remove-position-graph-v1` is a separately named development condition in the [recipe registry](../../engine/src/graybench/evaluation_recipes.py). Its [public contract and oracle](../../engine/src/graybench/task50_revision.py) preserve the Qiskit circuit-editing task. Given a nonempty circuit and a valid nonnegative instruction position, return the circuit with exactly that instruction removed. Modifying the supplied circuit and returning a separate circuit are both permitted. Remaining operations, their types, names, dimensions, finite definitions, exact numeric parameters, ordered wire assignments, bit/register types, register names/sizes/memberships and global phase must be preserved. Circuit names, metadata and operation labels are unscored. This clarifies instruction indexing, including barriers, resets and measurements; it is an adapted correctness condition, not an untouched upstream score.

Normal supplies a Qiskit import and function prefix; hard supplies the same requirements and entry-point name without imports or an implementation prefix. No examples, replacement algorithm, solution hints or private cases are sent to generation. Campaign planning applies the revision before preparing requests and freezes the revised task, request and judge identities. The revision accepts only the exact pinned source record or its exact idempotent revision; changing its canonical answer, difficulty, task identity, prompt or test cannot silently claim that ancestry.

The oracle prepares the expected remainder before candidate dispatch, independently reconstructing it from retained instructions. It exercises every position across six circuits, totaling 25 calls per answer: one instruction, duplicated instructions, the original four-instruction example, parameterized gates with phase, multiple quantum/classical registers, and mixed gates/barriers/reset/measurement. It compares ordered instruction signatures rather than relying on circuit equality. Numeric parameter comparison is exact because circuit editing need not approximate numbers. Gate equality alone was insufficient: SDK equality can tolerate parameter differences or omit names and definitions. Definitions are normalized on mutable operation copies, so checking them does not populate captured public singleton caches.

The [authored control module](task50_protected_graph.py) contains four accepted styles (in-place deletion, copied deletion, reconstruction, and changed unscored names/metadata/labels) and nine incorrect styles. Both suites therefore have 26 declared control trials: eight expected passes and eighteen expected failures. Local tests execute these authored functions only. Additional direct and real graph round-trip regressions reject changed register families, operation names and definitions; another rejects a tiny parameter change. Positive graph round trips check all 25 calls for copied and mutated outputs, including the returned alias for in-place edits.

To freeze a development campaign from `engine/`:

```sh
uv run graybench campaign-plan model.json CACHE task50-setup.json --name task50-development --image sha256:IMAGE_DIGEST --evaluation-recipe qhe50-remove-position-graph-v1 --task normal/qiskitHumanEval/50 --task hard/qiskitHumanEval/50
```

Once Docker is healthy, the authored control command is:

```sh
uv run python ../docs/reliability-evidence/task50_protected_graph.py --cache CACHE --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --output NEW_RESULTS.jsonl
```

That command reserves a new append-only control log, predeclares the judges, and inspects the recorded chain. It performs no model request. Docker control execution remains pending; local round trips do not establish container isolation, worker integrity or resource calibration. The 25 inputs are not exhaustive proof for arbitrary circuits, custom instructions or symbolic/recursive definitions. Definition normalization has a depth guard of 16; the authored inputs have shallow finite definitions. Graph output does not attest native object provenance or construction methods. Independent Qiskit task-card review, requirement-to-case admission and release qualification remain missing; `release_eligible` is false.

The broader cache-enabled check also exposed tests that incorrectly called October 6 logs current-source evidence. Those tests now preserve the actual records as historical and require dated builders to reject stale-source reuse. Native verifier unit tests use explicitly synthetic temporary metadata bindings with the historical worker messages as fixtures; these are not new observed executions or rescored models. Production verifiers and committed evidence bytes are unchanged.

For Windows reproduction, the deeply nested checkout's Qiskit import failed even though its wheel record and module file existed. Installing the same locked Python 3.12.14/Qiskit 2.4.2 dependencies into the shorter `gb-qiskit-20261007` environment restored import. Tests requiring Qiskit and the pinned cache were enabled for final verification; Docker-dependent cases remain separate.

October 7 verification with that locked environment and the pinned cache: the full engine suite completed with **1,386 passed, 283 skipped, zero failures** in 182.27 seconds, with 12 Windows temporary-directory cleanup warnings. `GRAYBENCH_TEST_IMAGE` was unset. The task-50 focused suite completed with 12 passes and one Docker-dependent skip. Ruff lint and formatting passed using `engine/pyproject.toml`. Two code reviews checked the oracle and historical-evidence test changes; their identified register-family, operation-name, definition and regression-coverage gaps were repaired and retested. These are implementation reviews, not independent benchmark admission attestations.

The operation/circuit distinction and copy behavior are documented in [Qiskit 2.4 QuantumCircuit](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.circuit.QuantumCircuit). The local implementation and controls establish this condition's behavior; the documentation alone does not prove oracle adequacy.

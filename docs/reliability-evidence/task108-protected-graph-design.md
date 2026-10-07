# Task 108: all Choi return values

The original normal/hard task requests a first Choi matrix, its channel adjoint, and composition with a second matrix. Its single identity input checks only the second value. The separately selected development condition `qhe108-choi-values-graph-v1` retains the entry point, normal completion versus hard standalone format, and three Qiskit Choi outputs. Original task bytes and diagnostic results remain unchanged.

The public contract accepts same-sized finite complex NumPy matrices of shape `(4**n, 4**n)` for positive `n`, representing square maps on `n` qubits. Complete positivity and trace preservation are not assumed: the original accepts general matrix data. It explicitly defines composition as the second channel after the first, and adjoint as the channel adjoint, rather than a Hermitian transpose of the Choi matrix. Inputs may be modified, provided the results describe their original values. Return-value aliasing and mathematically equivalent constructions are accepted. Dimensions and all three finite data matrices are checked at absolute tolerance `1e-8` and relative tolerance `1e-10`. No internal construction method or object provenance is attested.

The trusted checker computes expectations from the Choi definition using indexed blocks and complex conjugation, without calling candidate-side `Choi.adjoint` or `Choi.compose`. It freezes expectations before dispatch. The fixed corpus exercises one-, two-, and three-qubit inputs: complex noncommuting unitary channels, nonunital amplitude damping, non-Hermitian linear maps, zero maps, and the original identity-matrix witness. These are authored finite witnesses, not proof of every input in the public domain.

Campaign planning must revise the prompt and checker before preparing provider requests, bind exact pinned source ancestry and the entire judge manifest, require graph protocol 4 with delta transport and individual calls, and reject changed source bytes or unsupported families. The condition is never an implicit fallback for the native or upstream graph tracks.

Initial round trips hit the default cumulative array bound, then the cumulative matrix bound; both are 512 KiB. The condition therefore freezes 4 MiB for each retained-storage category and 16 MiB for expanded state, wire messages and accumulated output. Delta encoding reduces repeated transmission while retaining every exported node, including objects no longer in current roots. The original graph defaults remain unchanged; the shared validator permits explicit storage bounds up to 16 MiB. Both runtimes receive the exact same frozen record. This is local corpus calibration, not a universal allowance for arbitrary candidate histories or proof of container resource adequacy.

Planning also must record each recipe's actual output default. BB84 v2 previously used 16 MiB when first constructing its judge but serialized the generic 1 MiB setup default, making later judge reconstruction inconsistent. The builder now freezes the selected recipe default in both stages; historical setup records are preserved and are not silently rewritten.

Implementation and verification sequence:

1. Reproduce the unavailable campaign condition with a failing plan/reconstruction test.
2. Add exact-source revision and independent block oracle; wire the explicit recipe into planning.
3. Check independently authored correct constructions and targeted incorrect returns, adjoint conventions, composition order, dimensions, nonfinite values, and input mutation.
4. Round-trip the entire corpus through graph encoding and decoding; predeclare controls for later isolated execution in an append-only review log.
5. Review the code, run the locked offline regression suite, preserve historical artifacts, and record the exact verified source.

Docker is unavailable at design time. Local execution of trusted authored fixtures is allowed, but it cannot be described as isolated judging. Protected container controls, uniform resource calibration, independent task admission, and publication eligibility remain pending. Do not execute model-generated code directly on the host.

[Qiskit 2.4 documentation](https://eu-de.quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.quantum_info.Choi) defines the input/output block convention and channel-adjoint and composition behavior. The [pinned Qiskit implementation](https://github.com/Qiskit/qiskit/blob/2.4.2/qiskit/quantum_info/operators/channel/choi.py) provides a separate SDK reference for local oracle calibration; agreement alone is not independent admission.

The [implementation](../../engine/src/graybench/task108_revision.py) and [authored control runner](task108_protected_graph.py) now provide this condition. Each suite predeclares four accepted implementations (direct SDK construction, a SuperOp matrix product, permitted input mutation, and a perturbation inside tolerance) and ten rejected implementations. The latter cover wrong first/composed values, the wrong adjoint, reverse composition, Choi matrix multiplication, nonfinite data, wrong dimensions/count, an unwanted phase, and an out-of-tolerance perturbation. Local tests execute only these trusted authored fixtures, never saved model answers on the host.

Round trips run the complete 19-pair corpus for direct, SuperOp, and input-mutation implementations through the declared delta arenas, retaining early node IDs through the final call and checking accumulated serialized traffic against the output bound. The initial tests also exposed and repaired missing propagation of explicit limits to the worker: the host constructor now receives the frozen limits, candidate staging writes their exact record, and the worker reads it. Separate red-to-green staging tests cover that path without starting Docker; invalid type, downgrade and state/transport disagreement are rejected before staging. These checks are not observed container execution.

From `engine/`, a development plan can be frozen with:

```sh
uv run graybench campaign-plan model.json CACHE task108-setup.json --name task108-development --image sha256:IMAGE_DIGEST --evaluation-recipe qhe108-choi-values-graph-v1 --task normal/qiskitHumanEval/108 --task hard/qiskitHumanEval/108
```

Once Docker is healthy, the authored isolated-control command is:

```sh
uv run python ../docs/reliability-evidence/task108_protected_graph.py --cache CACHE --image sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd --output NEW_RESULTS.jsonl
```

The runner reserves a new append-only review log, predeclares judge manifests, and inspects its recorded chain. It makes no model call. A pending log must be adjudicated rather than replayed under the same output name. The finite witness corpus, resource defaults, and graph reconstruction still need isolated controls, broad alternative calibration, independent requirement admission and external reproduction before publication.

October 7 verification used locked Python 3.12.14/Qiskit 2.4.2 dependencies, the pinned cache, and no Docker test-image setting. After the worker propagation fix, the full engine suite completed with **1,446 passed, 284 skipped, zero failures** in 187.19 seconds, with 12 Windows temporary-directory cleanup warnings. Engine digest: `9e7ad5f40f143fd868b2a3d193181e674b9c1f63ebb933a6fdd3b984a7c23ccc`. Ruff lint and formatting passed. A code reviewer checked the math, ancestry, planning and resource path, reproduced the missing-worker-bounds defect, and verified its repair with 45 focused passes and four skips. This is implementation review, not independent admission or container verification. Original artifact bytes and model answers were not changed.

# Experimental native graph storage and family 116

This is **development evidence, not benchmark admission or a model score**. The
original pinned image remains unchanged. The adapted runtime instruments two
SciPy 1.18.1 native allocation-return sites and exposes identity-bound,
capacity-checked storage helpers. The graph protocol can now preserve a
registered capsule, root array, and aliases, including a writable alias first
exported after its root became readonly. Private rehearsal replays the prior
root state and verifies that preparation does not write live storage.

The guarded development image is
`sha256:091248a8a17ce150a97363e66196c58de38893dd21d84a685d10e887e913c812`.
Its patched SciPy wheel is
`f7f82c02631cad19efbe6cc3e7863571761b4e80ef5022659e52291c5e932ed6`.
The [native/graph diagnostic record](GrayBench-native-graph-experiment-v2.json)
(SHA256 `85c4377d283af163f849c8f84008e3ab1f389259ac2a590d6e6f01914846b830`)
pins the image, wheel, patch/header/source hashes, exact test scripts and
results. All 11 cases passed, including the native address-sanitizer view and
reentrant-cleanup cases. Four protected Hamiltonian controls passed on this
image for snapshot and delta transport, with wrong-time solutions rejected.
These controls construct their matrices with ordinary NumPy allocation or
registered SciPy allocation; they do **not** prove support for the official
family-116 construction.

The first guarded image,
`sha256:d56e465c7f6a885fe885351ab255c123f878970006f940a22377fd27f5a2d3b0`,
crashed when the view helper was given an ordinary owning ndarray whose base
is null. The [red diagnostic record](GrayBench-native-graph-experiment-v2-red-null-root.json)
retains that failure (`check_registered_view.py`, exit 139). A null-base check
in the helper removed it; the actual header also passed the view rejection
cases under AddressSanitizer before the corrected wheel was built.

The [official reference replay](GrayBench-v4-hamiltonian-reference-adapted.jsonl)
(SHA256 `b4da6315b528935ece35ebf079beebf8ac71472025d88544f37359e450207271`)
completed for normal and hard `qiskitHumanEval/116`, but both outcomes remain
`unsupported`: `WireError: External array buffer requires a graph codec` on
the first call. The canonical solution calls `MatrixExponential.synthesize` on
a `PauliEvolutionGate`. Its returned `HamiltonianGate` parameter is a NumPy
view of another NumPy array whose base is a Rust `PySliceContainer`, rather
than the SciPy capsule handled by this experiment. A targeted runtime probe
found a 2×2 complex view, a four-element complex base array, and that opaque
Rust owner; Python exposes no buffer interface on the container. The
[focused probe](family116_storage_probe.py) and its
[observation](family116-storage-observation.json) pin that finding to the
adapted image. The
[rust-numpy source](https://docs.rs/numpy/latest/src/numpy/convert.rs.html)
documents this owner type for Rust-backed NumPy arrays. The
[original](GrayBench-v4-hamiltonian-reference-before.jsonl) and
[registry-only](GrayBench-v4-hamiltonian-reference-registry-only.jsonl)
reference replays also remained unsupported. These are interface findings, not failures of the
official solutions and not model scores.

The next step for family 116 is to find a reviewed reconstruction of that
Rust-backed ownership and alias relationship, or keep the family explicitly
unsupported until an openly specified, validated semantic revision is chosen.
Silently copying the matrix would change observable base/alias behavior and is
not an admissible fix. This experimental image has unpinned build dependencies
and has not been admitted for scoring.

The Docker-enabled regression suite on the original pinned image exposed an
overstated expectation in the synthetic Hamiltonian test: two valid-path
variants expected `pass` even though this image correctly returns
`unsupported` at the external-array buffer boundary. The test now checks that
exact unsupported detail on the baseline image, retains the wrong-time
`fail` expectation, and expects a valid-path pass only when run on another
explicitly selected image. This changes no runtime codec and does not admit
the experimental image or family 116.

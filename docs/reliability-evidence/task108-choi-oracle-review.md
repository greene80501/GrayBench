# Task 108: one identity input leaves two returned Choi values unchecked

Both pinned prompts require the `Choi` representation of supplied `data1`,
its adjoint, and the composition of the `data1` and `data2` Choi values, in
that order. The unmodified normal and hard tests call the candidate only
with `data1 = data2 = np.eye(4)`. They check the types and the first value's
dimension, then compare only the adjoint value's data with the identity
matrix. The first and composed values are never compared with their inputs.

The [exact-test probe](task108_native_oracle_probe.py) ran four trusted
authored implementations against each pinned test in the Python 3.12.14 /
Qiskit 2.4.2 image, with network disabled. The reference passed. A mutant
that ignores `data2` and returns the first `Choi` as the composition passed;
a mutant that returns a zero `Choi` as the first value also passed. A
wrong-adjoint control failed. The probe then used distinct valid unitary
X and Z channels as an independent witness: the ignored-`data2` composition
did not equal the actual composition, and the zero first value did not equal
the supplied X channel. The reference matched all three expected values.

The [saved eight-case result](GrayBench-task108-native-oracle-probe.json) has
SHA-256 `e7b76112384e0834a320a474cf309936446d819a638b004e86e686845449f72b`.
It binds the authored source, pinned dataset and task digests, runtime/image,
exact-test outcomes and X/Z witnesses. No model or external service was
called. This is native authored oracle evidence, not protected judging or a
benchmark score.

A separately versioned semantic contract should test multiple independent
valid channel pairs and compare all three returned Choi matrices to their
specified values, while accepting mathematically equivalent constructions.
The pinned tests remain unchanged for historical native reproduction. Both
task variants remain release-ineligible until independent review and a
defensible protected value contract are complete.

The later [all-value development condition](task108-protected-graph-design.md)
implements a separately selected public contract and indexed-block oracle.
It preserves these exact native diagnostics. Local authored controls and graph
round trips do not replace protected execution or independent task admission.

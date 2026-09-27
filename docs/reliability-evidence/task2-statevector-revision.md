# Task 2: separately versioned Bell-state development recipe

`qhe2-bell-statevector-v1` is an opt-in development recipe for both pinned
normal and hard task 2. The original task records, upstream tests and historical
scores remain unchanged. The revised public request explicitly requires a
Qiskit two-qubit `Statevector` representing Phi+, allows global phase, and
declares absolute amplitude tolerance `1e-10` with zero relative tolerance.
That is a scoring-contract change, so its results must not be mixed with the
upstream track.

The trusted test requires `Statevector` and dimensions `(2, 2)`, copies the
four complex amplitudes from the object's raw instance state, rejects non-finite
values, aligns global phase using the overlap with Phi+, and compares
amplitudes. It never calls the candidate object's `equiv`, `data` or `dims`
accessor. The recipe, revised public prompt, test, source and
runtime are bound into the campaign judge and request identities. Its manifest
marks it `release_eligible: false`.

Local Python 3.12 / Qiskit 2.4.2 tests exercise both normal and hard forms.
The revised native checker accepts canonical, H/CX circuit-derived,
global-phase and near-tolerance states. It rejects plain equivalence claims,
wrong-amplitude subclasses that override `equiv` or `data`, Phi-minus, a product state,
ququart dimensions, an unnormalized state, a value outside tolerance, and NaN.
The exact pinned normal and hard canonical solutions also pass the revised
native checker after their public prompts are assembled. Their original task
digests are `a78bfe9a998849b69a9fb0b4e781a2a1d3299e2b89948eae7842d9594f4a429f`
and `3eade3264d5638c1bd66d1a9630d9388137498b2b98e202066c3ddeb49784d88`;
the corresponding revised digests at this source are
`5c39825648bedce73631647080ec48968d886b9e902bd233bbe9085654b7b262`
and `5056e3d0244d20ee18e70620799639ec7ae876f4ed230059bb97d28e22b9c157`.
These are **native checks**, not protected-judge outcomes.

Protected positive and adverse controls are retained in
`engine/tests/test_bell_revision.py` and require `GRAYBENCH_TEST_IMAGE`.
They are currently skipped because Docker Desktop cannot start. A review found
that the protocol-3 candidate-side codec previously read patchable `data` and
`dims` accessors; an exact class object storing `|01>` could therefore be
serialized as Phi+ after a class-level property patch. A red/green local codec
regression now reads validated raw instance data and subsystem fields for exact
`Statevector` objects. The Docker-gated cases include these accessor forgeries
and a global-phase positive, but have not run. The codec still excludes
subclasses, which can therefore be `unsupported` rather than graded failures.
More broadly, candidate code shares a process with its encoder and could patch
the encoder itself; the
[local worker integrity probe](worker-encoder-integrity.md) demonstrates that
remaining false pass. Raw-field reads do not establish tamper-proof serialization.
This recipe checks the reconstructed returned value, not how it was built.
Independent domain review, protected normal/hard controls, worker-boundary
hardening, resource calibration and full task-card admission remain open. No
model generation or score was produced for this recipe.

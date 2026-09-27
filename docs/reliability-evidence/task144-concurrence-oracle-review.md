# Task 144: positive and negative concurrence controls

Both pinned prompts ask for a list of ten density matrices whose concurrence
is zero. The unmodified normal and hard tests check the list length, require
each item to be a `DensityMatrix`, and call Qiskit's `concurrence(item) == 0`.
They do not require randomness, distinct matrices, or use of
`random_density_matrix`; the canonical implementation's sampling loop is one
valid approach, not a public requirement.

The [diagnostic script](task144_oracle_probe.py) ran the pinned tests through
the current protected bridge in image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
with Python 3.12.14 and Qiskit 2.4.2. In each suite, the canonical answer,
ten pure product states, and ten varied product states passed. Three invalid
controls failed: nine states, ten non-`DensityMatrix` values, and ten Bell
density matrices with concurrence approximately one. The
[saved 12-case result](GrayBench-task144-oracle-probe.json) has SHA-256
`0a44bce1bdfb1d6366532592055379fa4580416c2024367c90af22d6e78c49b7`.
It records the pinned dataset revisions, task and completion digests, image,
runtime, and judge digest. No model or external service was called.

These controls support the basic stated count, type, and concurrence boundary
for both variants. They do not establish stability near numerical zero,
complete alternative coverage, native same-process parity, or immunity to
candidate-side encoder substitution. Task admission still needs those checks,
independent review, and a frozen release decision. This result is development
evidence, not a model score or a release eligibility change.

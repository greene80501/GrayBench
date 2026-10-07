# Task 126: a constant result passes without the requested computation

Both pinned prompts ask for Hadamard-derived operators that differ only by
global phase and for their process fidelity. The tests check only that the
candidate returns a float within `1e-6` of 1.0. No operator construction or
fidelity calculation is observed.

The [six-case protected-bridge probe](task126_oracle_probe.py) evaluates the
unchanged normal and hard tests in the Python 3.12 / Qiskit 2.4.2 image. The
canonical reference passes both. `return 1.0` also passes both without using
Qiskit; a `return 0.0` control fails both. These are authored controls, not
model responses or certified scores.
The [saved six-case result](GrayBench-task126-oracle-probe.json) has SHA-256
`0cff91fd21fb7b28c7b7a44799ddbf11da3a3fa2b94960793f7398d2bab2ceec`.
It binds the pinned tasks, candidate and judge digests, evaluator image, and
runtime versions. No model or external service was called.

The prompt requests a computation method, but its no-argument output is fixed
for every valid pair that differs only by global phase. An output-only test
cannot establish that the method was used. The historical upstream result can
be reported as such, with this limitation disclosed. A separately versioned
semantic task must either score only the output it actually observes or ask
for fidelity on varied input operator pairs, including pairs that do not
differ merely by global phase. Both pinned task variants remain
release-ineligible.

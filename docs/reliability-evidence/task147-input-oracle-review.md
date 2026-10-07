# Task 147: a fixed circuit can discard the input

Both pinned prompts ask the candidate to add a four-controlled Y on qubit 4
to the supplied circuit, using qubits 0–3 as controls. Both tests supply only
one six-qubit input that begins with H gates on qubits 0, 4 and 5, then
compare the returned operator with that input plus the controlled Y. They do
not exercise another valid input circuit.

The [exact-test probe](task147_oracle_probe.py) ran ten authored cases against
the unmodified normal and hard tests in the immutable Python 3.12.14 /
Qiskit 2.4.2 image with network disabled. The canonical reference passed.
An independent correct construction using `S†`, multi-controlled X and `S`
on the target also passed. A candidate that ignores its argument and always
returns the prebuilt circuit for the tested H-gate input passed both suites.
It failed a separate operator comparison for a valid input with X on qubit 5;
the reference and the independent construction preserved that input. The
unchanged-input and uncontrolled-Y controls failed in both suites. The normal
`check` was invoked explicitly; the hard test invokes it itself. No model API
request was made.

The [saved UTF-8 result](GrayBench-task147-exact-oracle-probe.json) has SHA-256
`b15949dd3cc88be0469db39b377be667a6a3c428d23296093c8fbf82e232162c`.
It binds the source, dataset pins, task digests, candidate hashes, runtime,
ten exact-test outcomes and alternate-input operator witnesses. This is
authored native diagnostic evidence, not a protected-judge run or benchmark
score.

A separately versioned semantic oracle should compare the returned operator
with the input followed by the requested controlled-Y across varied valid
circuits, accepting equivalent gate decompositions. Keep historical upstream
tests unchanged; task 147 is not admitted for a verified score.

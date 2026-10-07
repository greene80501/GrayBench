# Task 150: loop structure is checked, but stopping behavior is not

Both pinned prompts require a `for_loop` over `n` iterations, an `RY` rotation
depending on the iteration index, a Hadamard, a CX, a measurement, and a
conditional break when the measured bit equals `1`. The normal and hard tests
call the candidate only with `n=2`. They inspect the loop's first four body
instructions and require its fifth instruction to be an `IfElseOp` connected
to the expected qubits and classical bit. They do not inspect the branch's
condition value or body.

The [exact-test probe](task150_oracle_probe.py) ran 12 authored cases against
the unmodified normal and hard tests in the immutable Python 3.12.14 /
Qiskit 2.4.2 image with network disabled. The canonical reference passed in
both suites. Three faulty variants also passed in both: a branch containing
`cx` instead of `break_loop`, a branch that breaks when the bit is `0`, and a
function fixed to `range(2)` that ignores `n`. The probe independently called
each passing function with `n=3` and recorded its loop indices, branch value,
and branch operations. For the fixed-count variant those indices were `[0, 1]`
instead of `[0, 1, 2]`. Wrong-rotation and wrong-range controls failed in
both suites. The normal `check` was invoked explicitly; the hard test invokes
it itself. No model API request was made.

The [saved UTF-8 result](GrayBench-task150-exact-oracle-probe.json) has SHA-256
`d4e0d1a3636f96b45ba606ec57cb4fa634330727693a63ac6566e13769eda0b0`.
It binds the source, dataset pins, task digests, candidate hashes, runtime,
12 exact-test outcomes and `n=3` structural witnesses. This is authored native
diagnostic evidence, not a protected-judge run or benchmark score.

A separately versioned oracle should check the nested control-flow semantics
and exercise multiple valid `n` values. The task's explicit operation and
control-flow requirements can be checked without relying on only the
reference's incidental circuit serialization. Keep historical upstream tests
unchanged; task 150 is not admitted for a verified score.

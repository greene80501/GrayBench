# Task 139: the oracle does not validate the decomposition

Both pinned prompts ask for the Schmidt coefficients and subsystem vectors of
the supplied statevector and partition. Both tests pass one random 16-dimensional
state and partition `[0, 1]` to the candidate, then inspect only the entries
returned. They check nonnegative coefficients and two-qubit subsystem dimensions,
but do not require any entries, verify coefficient normalization, compare the
reconstructed state, or exercise another partition.

The [exact-test probe](task139_oracle_probe.py) ran ten authored cases against
the unmodified normal and hard tests in the immutable Python 3.12.14 / Qiskit
2.4.2 evaluator image with network disabled. The canonical reference passed in
both suites. An empty list passed because the assertion loop never ran. A
function returning the same single term, `1.0 × |00⟩ × |00⟩`, for every input
also passed, even though that term represents `|0000⟩` and cannot reconstruct
a distinct input such as `|1111⟩`. Negative-coefficient and wrong-dimension
controls failed in both suites. The normal `check` was invoked explicitly;
the hard test invokes it itself. No model API request was made.

The [saved UTF-8 result](GrayBench-task139-exact-oracle-probe.json) has SHA-256
`e6d435835b68b5bdb084718d842bd6dcc3e26bc11eea3c640c9fac97801ebb63`.
It binds the source, dataset pins, task digests, candidate hashes, runtime and
ten outcomes. This is authored native diagnostic evidence, not a protected
judge run or benchmark score.

A separately versioned semantic contract should check complete reconstruction
against varied valid inputs and partitions, with an explicit tolerance and
phase convention. It should accept mathematically equivalent decompositions,
including phase choices and degenerate Schmidt bases, rather than comparing
one exact factorization. Keep the historical upstream tests unchanged; task
139 is not admitted for a verified score.

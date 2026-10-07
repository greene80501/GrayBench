# Task 140: entropy does not establish a probability vector

Both pinned prompts request ten probability vectors of length 16 with Shannon
entropy above a supplied threshold. The normal and hard tests call the
candidate once at threshold `1`, check the list length and each vector's
length, and call Qiskit's `shannon_entropy` on each vector. They do not check
that the entries are finite, nonnegative, or sum to one. The public wording
says “greater than,” while the test uses `>=`; the normalization defect is
independent of that boundary distinction.

The [exact-test probe](task140_oracle_probe.py) ran ten authored cases against
the unmodified normal and hard tests in the immutable Python 3.12.14 /
Qiskit 2.4.2 image with network disabled. The canonical reference and a
valid uniform distribution passed in each suite. Ten copies of a vector
containing sixteen `0.1` entries also passed, even though each vector's total
mass is `1.6`; pinned Qiskit returns approximately `5.3151` for its Shannon
entropy. Wrong-length and zero-entropy controls failed in both suites. The
normal `check` was invoked explicitly; the hard test invokes it itself. No
model API request was made.

The [saved UTF-8 result](GrayBench-task140-exact-oracle-probe.json) has SHA-256
`d63fa6b83b243bedd3af875f69e94fb60c6af80352b52891974d616a5f1fffe4`.
It binds the source, dataset pins, task digests, candidate hashes, runtime,
invalid vector mass and ten outcomes. This is authored native diagnostic
evidence, not a protected-judge run or benchmark score.

A separately versioned semantic contract should validate probability-vector
semantics before applying the declared entropy threshold, and exercise more
than one valid threshold. It should not require the reference's particular
random generation method unless that is made a public requirement. Keep the
historical upstream tests unchanged; task 140 is not admitted for a verified
score.

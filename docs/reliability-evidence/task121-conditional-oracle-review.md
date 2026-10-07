# Task 121: conditional correction is not checked

Both pinned prompts require a one-qubit, two-classical-bit circuit named `c`:
apply a Hadamard to randomize the qubit, measure it, conditionally apply **X**
when the first result is 1, then measure the corrected qubit. The original
tests check the qubit/bit counts, the presence of `h` and `if_else` operations,
and simulated counts with no final classical bit set. They do not inspect the
conditional body or require two measurements. The normal test's `check` was
invoked explicitly; the hard test invokes `check` itself.

The [exact-test probe](task121_oracle_probe.py) ran in the immutable Python
3.12.14 / Qiskit 2.4.2 evaluator image against both content-pinned records.
The canonical answer passed each test. A circuit that keeps both measurements
but places an identity operation in the conditional branch and **unconditionally
resets** the qubit before the second measurement also passed. A second circuit
removed the first measurement entirely, retained a nominal `if_else`, and
reset before its only measurement; it too passed. Both violate the public
conditional-correction requirement. An identity-only branch with two
measurements and no reset failed in each suite, demonstrating that the final
count check executes and detects an uncorrected output in this control.

The [byte-preserved result](GrayBench-task121-exact-oracle-probe.json) has
SHA-256 `2a239334ba77db6a5ca0d75a1a4b18e6510174643112333f162e224890666b1f`.
It records the pinned dataset and task digests, evaluator image, runtime,
probe-source SHA-256, candidate hashes, operation counts and eight outcomes.
No model was called. This is an authored native diagnostic, not a protected
judge run or a benchmark score.

A separately versioned checker should examine the conditional branch and
test both measured outcomes. It should check the promised X correction and
the register/measurement structure without insisting on the canonical source
text. If equivalent implementations that achieve the same conditional behavior
without an X gate are intended to pass, the public contract must say so before
generation. The historical tests remain unchanged; task 121 is not admitted
for a verified score.

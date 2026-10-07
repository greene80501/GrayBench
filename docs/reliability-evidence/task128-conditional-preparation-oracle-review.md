# Task 128: the XOR check does not establish Hadamard preparation

Both pinned prompts require a four-qubit circuit that applies Hadamard gates to
the first three qubits, measures them, conditionally applies X to the fourth
qubit based on their XOR, and measures the fourth. The normal and hard tests
check circuit type and dimensions, the existence of a one-qubit/three-clbit
`if_else`, and the XOR relation in sampled outcomes. They do not check that
the first three qubits were prepared with Hadamard gates or that more than the
all-zero branch can occur.

The [exact-test probe](task128_oracle_probe.py) ran eight authored cases against
the unmodified pinned tests in the immutable Python 3.12.14 / Qiskit 2.4.2
evaluator image. The canonical reference and an independently written
explicit-H-loop implementation passed in both suites. A circuit with the same
measurements and conditional X but **no Hadamard gates** also passed in both
suites. Its first three measurements are always zero, so its fourth measurement
correctly equals their XOR without exercising nonzero branches. A circuit with
the required H gates but conditional Z instead of X failed in both suites.
The normal `check` was invoked explicitly; the hard test invokes it itself.

The [saved UTF-8 result](GrayBench-task128-exact-oracle-probe.json) has SHA-256
`8acff131d97ee8125c3528b3bf857fe833e5845c8cdfaf39ce2689394dedeb71`.
It binds the probe source, dataset pins, task digests, candidate hashes,
runtime, eight outcomes, and counts of H, measurement and `if_else` operations.
No model API was called. This is authored native diagnostic evidence, not a
protected-judge run or a benchmark score.

A separately versioned contract should state whether literal Hadamard
instructions are required or equivalent state preparation is acceptable.
Its checker should validate preparation under that public rule and exercise
both parity branches independently, without relying on 1,024 random samples
to cover the domain. Retain independently correct implementations and wrong
controls. Historical upstream tests remain unchanged; task 128 is not
admitted for a verified score.

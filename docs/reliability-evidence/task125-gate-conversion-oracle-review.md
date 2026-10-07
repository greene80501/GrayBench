# Task 125: the first gate's action is not checked

Both pinned prompts ask for a `Gate` equivalent to the action of any input
`QuantumCircuit`. The normal and hard tests each call the candidate on a
three-qubit H/CX circuit and a one-qubit H/X/H circuit. For the first call,
they check exact `Gate` type and qubit/classical-bit counts, but never compare
the returned gate's action with the input circuit. For the second call, they
compare the returned operator to Z. The tests do not exercise another circuit
or a different width.

The [exact-test probe](task125_oracle_probe.py) ran ten authored cases against
the unmodified pinned tests in the immutable Python 3.12.14 / Qiskit 2.4.2
evaluator image. The canonical reference and an independent `circ.to_gate()`
implementation passed in both suites. An authored implementation that returns
an unrelated three-qubit `Gate` for the first input and a fixed Z gate for the
second also passed in both suites. Its first gate does **not** implement the
first circuit's action. A wrong first width and a wrong second operator each
failed in both suites, confirming that those asserted properties were
exercised. The normal `check` was invoked explicitly; the hard test invokes
it itself.

The [saved UTF-8 result](GrayBench-task125-exact-oracle-probe.json) has SHA-256
`5d967f00b851238fbc82200e1a6fe3c6410eaf9740e79ddbbbad8fc2ae951bc6`.
It binds the probe source, dataset pins, task digests, candidate hashes,
runtime, ten outcomes and a separate first-action equivalence check. No model
API was called. This is authored native diagnostic evidence, not a
protected-judge run or a benchmark score.

A separately versioned checker should compare the returned gate's operator
with each input circuit over varied valid widths and gate compositions, up to
physically irrelevant global phase. It should retain a public policy for
nonunitary or parameterized inputs rather than silently assuming behavior
outside the declared domain. Include independent correct conversions and
mutation controls so the test does not demand one implementation style.
Historical upstream tests remain unchanged; task 125 is not admitted for a
verified score.

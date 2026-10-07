# Task 145: the zero-qubit assertion is swallowed

Both pinned prompts request an inverse QFT circuit for `n` qubits. The tests
check the returned circuit and operator for several positive values. They also
attempt a zero-width edge check that says the candidate may raise or return an
empty circuit. That assertion is inside `try/except Exception`, so the test
catches its own `AssertionError` when the candidate returns a nonempty circuit.

The [pinned protected-bridge probe](task145_oracle_probe.py) runs the unchanged
normal and hard tests in the Python 3.12 / Qiskit 2.4.2 evaluator image. The
canonical reference passes both. A mutant returns the correct inverse QFT for
positive sizes but a one-qubit circuit for `n=0`; it also passes both. An
identity-circuit control fails the positive-size operator checks in both.
The [saved six-case result](GrayBench-task145-oracle-probe.json) has SHA-256
`0a8cc722207832cdda16d074fa1f7bc86df9e3d5609be5ead3a178616ecedf6c`.
It binds the pinned task, code and judge digests, evaluator image, runtime
versions, and observed outcomes. No model or external service was called.

The public prompt does not explicitly define whether zero is a valid width.
Consequently the observed acceptance is evidence that the test's *stated*
zero-width policy is unenforced, not authority to impose a new zero-width
requirement on historical model answers. Keep the pinned upstream tests
unchanged. A separate semantic release must declare the input domain and edge
behavior before generation, then check that rule without swallowing assertions.
Both task variants remain release-ineligible.

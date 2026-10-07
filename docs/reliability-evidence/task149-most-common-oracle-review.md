# Task 149: first returned string passes a majority test

Both pinned prompts request the most common bit string from a `BitArray`.
Their three test inputs are constructed from count dictionaries whose first
entry is always the most frequent. The tests do not vary input order.

The [pinned protected-bridge probe](task149_oracle_probe.py) tests the unmodified
normal and hard records in the Python 3.12 / Qiskit 2.4.2 evaluator image.
The canonical solution passes both. A deliberately wrong implementation that
returns `bits.get_bitstrings()[0]` also passes both; a last-string control fails
both. For a valid counterexample with counts `{"101": 3, "001": 50}`, the wrong
implementation returns `"101"` while the most common result is `"001"`.
The [saved six-case result](GrayBench-task149-oracle-probe.json) has SHA-256
`5bfda95e011e3cba944e2abeb15d0e097cdba0aec588a7d1c291ad60c01c823d7`.
It records dataset and task digests, candidate and judge digests, image and
runtime versions, outcomes, and the reversed-order witness. No model or
external service was called.

The probe uses the same frozen extraction rule and protected judge as the
development recipe. It is oracle evidence, not a model score or task admission.
The upstream tests must remain unchanged for historical reproduction. A
separately versioned semantic contract should test differing count and order
patterns, define tie behavior, and accept any implementation that returns the
correct result. Both task variants remain release-ineligible.

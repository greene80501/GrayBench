# Task 119: ripple-carry adder kinds and widths

Both pinned public prompts request a `QuantumCircuit` with a
`CDKMRippleCarryAdder` for the supplied `num_state_qubits` and `kind`. They name
three supported kinds: `full`, `half`, and `fixed`. Both original tests compare
the returned operators only for `(3, "full")` and `(3, "fixed")`. There is no
call with `half` or with another valid width.

The [exact-test probe](task119_oracle_probe.py) ran both pinned tests in the
immutable Python 3.12.14 / Qiskit 2.4.2 evaluator image. The canonical
reference and a structurally different direct `CDKMRippleCarryAdder` return
passed in each suite. A deliberately restricted implementation
also passed both tests while raising `ValueError` for `(3, "half")` and
`(4, "full")`. Those are supported inputs in the pinned SDK. Separate
wrong-`full` and wrong-`fixed` controls failed as expected, showing that the
tested cases were actually checked. The normal `check` was invoked explicitly;
the hard source invokes it itself.

The [byte-preserved result](GrayBench-task119-exact-oracle-probe.json) has SHA-256
`aab48731e7052fd23c026d0934a341aaa74ff82d67de8e8f9d785f7a2bbe4d0f`.
It records both pinned task digests, dataset pins, evaluator image, runtime,
probe-source hash, candidate hashes, ten exact-test outcomes, and the direct
public-input controls. No model API was called. This is authored native
diagnostic evidence, not a protected-judge run or a benchmark score.

A separately versioned checker should sample all three kinds at multiple
declared valid widths, check circuit types and compare behavior to independent
expected operators or basis-state arithmetic under a calibrated resource
budget. It must accept equivalent circuit constructions rather than insisting
on the canonical wrapper's exact syntax. An internal call to a specific SDK
constructor cannot be inferred solely from operator equivalence and should be
handled explicitly if the public contract makes it mandatory. Historical
upstream tests remain unchanged; task 119 is not admitted for a verified score.

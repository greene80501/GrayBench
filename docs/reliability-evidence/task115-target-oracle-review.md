# Task 115: Target instructions and properties

Both pinned public prompts require a two-qubit `Target` with `UGate` on qubits
0 and 1, `CXGate` in both directions, UGate parameters named `theta`, `phi`, and
`lambda`, and nonzero duration **and error** properties for every instruction.
The original normal and hard checks count instructions by name and qubits and
require positive durations, but accept `error >= 0`. They do not inspect the
UGate parameter values or names. This is a test defect in the upstream track;
the historical tests and scores must remain unchanged.

The [exact-test probe](task115_oracle_probe.py) ran the pinned checks inside the
immutable Python 3.12.14 / Qiskit 2.4.2 evaluator image, with the task records
loaded from byte-verified pinned datasets. The normal check was called explicitly;
the hard test calls it in its own source. For **each** suite, the canonical
reference passed, and these authored wrong answers also passed:

- All four error properties changed to zero.
- `theta`, `phi`, `lambda` replaced with `x`, `y`, `z`.
- The symbolic UGate replaced with `UGate(0, 0, 0)`.

Negative error and zero duration controls failed in both suites. Thus the
probe actually reached the pinned assertions. The
[byte-preserved result](GrayBench-task115-exact-oracle-probe.json) has SHA-256
`0b369aeaddbef769896512041ec1c972761acd6196828fed0b5f517be885225e`;
it records both task digests, dataset pins, runtime, probe-source hash, case
hashes, and all 12 outcomes. It used no model API and is not a protected-judge
run or a benchmark score.

A separately versioned stronger task contract should check an actual two-qubit
`Target`, UGate/CXGate types and requested qargs, three UGate `Parameter` values
with the requested names in order, and finite, strictly positive duration and
error values for every listed instruction. A correct independently constructed
Target and deliberately wrong controls must pass/fail respectively before task
admission. Exact duration/error *magnitudes* were not specified publicly and
must not be imposed. Native `Target` transport and the worker-encoder integrity
boundary remain unresolved; this review does not make task 115 scorable.

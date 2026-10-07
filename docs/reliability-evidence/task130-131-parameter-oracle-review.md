# Tasks 130 and 131: the argument is not varied

Task 130's pinned normal and hard prompts require an inverse circuit with
`n` qubits and operations on the second through fifth qubits. Both tests call
the candidate only with `n=5` and compare the returned circuit with one exact
expected circuit. A function that always builds a five-qubit circuit passes
both tests, but returns five qubits for a valid `n=6` request.

Task 131's pinned prompts require a dictionary of properties for the named
local fake backend. Both tests request only FakeCairoV2. A function that always
returns FakeCairoV2's configuration passes both tests, but reports 27 qubits
when asked for FakeBelemV2, whose configuration has five. The latter call is
an independent diagnostic, not an added upstream test.

The [exact-test probe](task130_131_oracle_probe.py) ran 16 authored cases
against the unmodified pinned tests in the immutable Python 3.12.14 / Qiskit
2.4.2 evaluator image. For each task and suite, the canonical reference and
an independently written argument-sensitive alternative passed. The fixed
width/backend implementation also passed. A wrong-gate control for task 130
and a wrong-qubit-count control for task 131 failed. The normal `check` was
invoked explicitly; the hard test invokes it itself. The task-131 probe used
only local fake backends and made no IBM account or model API request.

The [saved UTF-8 result](GrayBench-task130-131-exact-oracle-probe.json) has
SHA-256 `5dd22b51fb36f5bdd50c154c5a97cbebd43e1a538dcb2d6fdadf3d3c14e0f5b1`.
It binds the probe source, dataset pins, task digests, candidate hashes,
runtime, 16 outcomes, and the observed results for untested valid inputs.
This is authored native diagnostic evidence, not a protected-judge run or a
benchmark score.

Separately versioned checkers should vary `n` across valid widths for task
130 and compare the inverse action under an explicit structural or semantic
contract. For task 131 they should vary fake-backend names and verify all
declared dictionary fields. Keep independent correct alternatives and
argument-ignoring mutations in the controls. Historical upstream tests remain
unchanged; neither task is admitted for a verified score.

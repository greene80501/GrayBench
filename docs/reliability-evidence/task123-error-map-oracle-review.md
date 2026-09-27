# Task 123: a blank error map passes

Both pinned prompts require a plot of the `FakeBelemV2` backend's error map.
The original normal and hard tests check only the exact `Figure` type, five
axes and the suptitle `fake_belem Error Map`. They do not inspect any plotted
content or compare backend error values.

The [exact-test probe](task123_oracle_probe.py) ran both pinned tests in the
immutable Python 3.12.14 / Qiskit 2.4.2 / Matplotlib 3.10.1 evaluator image.
The canonical reference passed with data on four of its five axes. An authored
`Figure` with five empty axes and the expected suptitle also passed in both
suites; none of its axes had plotted data. A wrong-title control and a
four-axis control failed in both suites, confirming that the checked
properties were exercised. The normal `check` was invoked explicitly; the
hard test invokes it itself.

The [byte-preserved result](GrayBench-task123-exact-oracle-probe.json) has
SHA-256 `6a08ef34bbf0be0f57c0e84edaf2a4b107b8ec75a2226e1c46a82a72736580d0`.
It binds the probe source, dataset pins, task digests, candidate hashes,
runtime and eight outcomes, including axis-data counts. No model API was
called. This is authored native diagnostic evidence, not a protected-judge
run or a benchmark score.

A separately versioned checker should validate that the figure depicts the
declared backend error data while allowing equivalent plotting layouts and
styles. It should use independently derived backend properties rather than
requiring the reference's exact artists or pixel image. Historical upstream
tests remain unchanged; task 123 is not admitted for a verified score.

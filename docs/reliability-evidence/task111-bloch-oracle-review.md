# Task 111: parameter count does not establish Bloch-sphere coverage

The normal and hard prompts ask for an ansatz to create pure states
distributed equally across the Bloch sphere with a minimum number of gates.
The exact pinned tests assert only that `candidate().num_parameters` lies
between two and five. They do not check the return type, qubit count,
prepared states, gate count, or a sampling rule for the parameters.

The [exact-test probe](task111_native_oracle_probe.py) ran five trusted
authored implementations against each unmodified pinned test inside the
Python 3.12.14 / Qiskit 2.4.2 image with network disabled. The reference
and an independently constructed one-qubit RY/RZ ansatz passed. A two-RZ
ansatz also passed despite creating only the starting physical state from
`|0>` at all nine parameter-grid points: its maximum measured `|1>`
population was zero. A two-qubit circuit passed despite not returning a
one-qubit Bloch-sphere ansatz. A one-parameter RY control failed. The
state witness compares density matrices, so a parameter-dependent global
phase is correctly treated as the same physical state.

The [saved ten-case result](GrayBench-task111-native-oracle-probe.json) has
SHA-256 `0de5b12a7d68d421ce596e31dc2e7c45cfca998e4b1cac5ed24c208cd7cf0b5b`.
It binds authored candidate hashes, pinned dataset and task digests,
runtime/image, exact-test outcomes, and state witnesses. No model or external
service was called. This is native authored oracle evidence, not a score.

Even a circuit capable of preparing every pure one-qubit state cannot by
itself establish an *equal distribution*: that depends on the parameter
sampling measure, which the prompt never defines. A separately versioned
contract should state whether it scores expressivity only or also a dataset
generator, define a one-qubit output and valid sampling rule, and use varied
state/coverage checks with independently correct alternatives. The pinned
tests remain unchanged for historical native reproduction. Both variants
remain release-ineligible pending review and an explicit protected contract.

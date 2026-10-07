# StatePreparation fidelity

The state_preparation_v1 record preserves original constructor input separately from current
parameters, plus integer/label mode and inversion. The original can be a bounded flat list or
tuple, a numeric array, Statevector, integer or Pauli label. Unsupported nested collections and
candidate-selected types are rejected. Dimensions are bounded to 15 qubits, flat collections to
32,768 values; scientific array byte bounds also apply.

The pinned SDK uses the stored parameters for synthesis and the original argument for inverse().
Consequently, reconstructing only from amplitudes or only from the original argument is lossy.
The decoder establishes a fixed StatePreparation object with a constant-size integer input and
restores these fields without normalizing or altering submitted values. This relies on reviewed
private fields in pinned Qiskit 2.4 and requires revalidation before a runtime upgrade.

Nineteen tests cover forward/inverse operators, qubit order, label/integer/vector modes,
preserved original types, modified non-normalized parameters, and malformed records. They also
preserve the SDK's inverse failure on an original non-normalized input and its integer inverse
dimension behavior. Separate task-5/task-6 reference replays pass in both normal and hard suites.
These are interface calibration evidence, not a complete reference scan or score certification.

Cached or user-modified instruction definitions, constructor-input aliases across returned
objects, and arbitrary custom subclasses are not fully represented. Those remain release gates
along with broader Qiskit interfaces and task-by-task specification/oracle verification.

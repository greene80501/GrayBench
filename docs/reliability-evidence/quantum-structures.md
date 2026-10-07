# Clifford, stabilizer and Choi transport

The typed scientific-value transport adds Clifford and unseeded StabilizerState boolean
tableaux, preserving destabilizer/stabilizer rows and phase bits. The shape and bool dtype are
validated, with a 256-qubit structural cap and existing byte limits. SDK symplectic validation
is disabled during reconstruction so invalid submitted values are preserved for the judge.
See the [Clifford representation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Clifford).

Choi values preserve exact numeric data and input/output subsystem dimensions, including
rectangular channels. No trace-preservation or positivity repair is performed. Shape and byte
limits remain enforced. See the [Choi API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Choi).

Tests cover tableau phases/composition, stabilizer operators, invalid symplectic values,
nonphysical rectangular Choi channels and malformed payloads. Seeded stabilizer RNG state and
explicit bound subsystem arguments are rejected rather than silently discarded. General RNG,
alias and subsystem-binding fidelity remain required interfaces.

Separate targeted reference replays pass normal and hard tasks 45, 92 and 108. These results
are compatibility evidence, not certified task scores. A new full offline reference scan runs
separately from an exact source-byte-verified checkout of commit 0a45d6a; it intentionally excludes
these later edits. Its evidence must not be relabeled as a scan of this change.

# Protected task-62 BB84 sender value revision

The pinned normal and hard Qiskit HumanEval task 62 asks for a sender `QuantumCircuit`. Both tests seed one five-qubit input and accept a fixed circuit that ignores `state` and `basis`; the preserved native probe demonstrates this false pass. The pinned native condition and its evidence remain unchanged. This revision adds a separately named, development-only protected value condition rather than pretending to repair the upstream score in place.

## Public contract

The candidate implements `bb84_sender_amplitudes(state, basis)`. The inputs are equal-length lists of binary integers, with length 1 through 5. `basis[i]=0` means Z; `basis[i]=1` means X. For each qubit `i`, `state[i]=0` or `1` selects `|0>` or `|1>` in Z and `|+>` or `|->` in X. The result is a list of `2**len(state)` `[real, imaginary]` pairs, in Qiskit's little-endian statevector order. Components must be finite and within `[-1,1]`. The host accepts global phase, checks norm and phase-aligned amplitudes with absolute tolerance `1e-10` and zero relative tolerance. Qiskit may be used, but only the returned value is checked; circuit identity or construction is not attested.

The normal prompt retains a function-completion prefix; hard requires a standalone function. Neither receives hidden cases, canonical code, or task-specific repair feedback. This is a different output contract from the upstream `QuantumCircuit` task, so scores from the two conditions cannot be combined or called exact upstream replication.

## Frozen checks and controls

The trusted host derives expected amplitudes directly from independent one-qubit BB84 factors and the documented Qiskit index convention, without running the candidate or the pinned canonical implementation. The private case set exhausts all binary `state` and `basis` pairs for widths 1, 2 and 3; additional predeclared width-4 and width-5 cases exercise larger vectors and mixed bases. Exact source digests for both pinned task records, all calls, the oracle implementation, the value runner and the immutable runtime image enter the judge manifest.

Positive authored controls include an analytic construction, a Qiskit `Statevector` construction and a global-phase variant. Wrong-answer controls include a fixed output, ignoring either input, incorrect qubit order and a wrong X-basis sign. The review log freezes the judge manifest before controls run and reports every expected and observed outcome. Passing these finite controls is not independent review or proof of correctness for every valid input.

## Release boundary

The revision enters the protected-task registry and can be explicitly selected for a development campaign. It remains `release_eligible: false`. The task-62 admission card keeps its unresolved upstream finding until reviewed evidence resolves it; authored controls do not fill independent-review or fixture-authenticity requirements. GitHub Actions remain disabled because of the account billing gate; local pinned-image validation is reported separately.

The bit and basis convention follows [IBM Quantum's BB84 explanation](https://quantum.cloud.ibm.com/learning/en/modules/computer-science/quantum-key-distribution). Statevector index ordering follows [Qiskit's bit-ordering guide](https://quantum.cloud.ibm.com/docs/en/guides/bit-ordering). These references support the mathematical contract, not GrayBench's test adequacy.

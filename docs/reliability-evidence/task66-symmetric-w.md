# Task66: symmetric W state and terminal measurements

## Separate public condition

The [original sampling diagnostic](task66-sampling-diagnostic.md) preserves the
pinned normal/hard prompts and checks. Under ideal independent shots, the private
count thresholds reject a correct equal-probability distribution about 0.77566%
of the time. The count assertions cannot distinguish relative-phase changes with
the same computational-basis probabilities. These are conditional arithmetic and
assertion observations, not an observed sampler failure rate or a full native
false pass. The original phase intent remains unadjudicated.

`qhe66-symmetric-w-measurement-graph-v1` is a new development condition. It
explicitly chooses the symmetric state
`(|001> + |010> + |100>)/sqrt(3)` in `|q2 q1 q0>` order, from initial `|000>`.
This phase choice is public before generation. It does not silently replace the
original task or make its scores comparable with the revised condition.

Return a plain three-qubit QuantumCircuit with three to 64 classical bits.
Prepare the target, then measure every qubit exactly once into distinct classical
bits in the computational basis. Measurement order, mapping, register names and
unused classical bits are unrestricted. No preparation operation may follow the
first measurement; barriers are allowed anywhere. Numeric unitary Gate
operations, Reset and Initialize are allowed before measurement. Classical
control, control flow, delays, unbound parameters, other channels and nonfinite
parameters/matrices are outside the contract.

Generic Gate, Instruction and ControlledGate effective definitions are expanded,
including nested terminal measurements. At most 16 active effective composite
definition levels below the returned circuit and 1024 visited instruction entries
are allowed. Composite entries count. A generic ControlledGate's effective
definition includes Qiskit's open-control X wrappers; these count too. Registered
SDK operations are evaluated as primitives, without counting their internal
synthesis definitions. These resource choices are stated in both public prompts;
the checker does not select a favorable gate sequence or constructor. The
[pinned ControlledGate implementation](https://raw.githubusercontent.com/Qiskit/qiskit/2.4.2/qiskit/circuit/controlledgate.py)
defines the effective open-control wrapper behavior used here.

The normal prompt retains its original imports, annotated no-argument signature
and function-completion format. Hard states the same requirement and requests a
standalone `w_state()` function. Exact pinned ancestry, including the canonical
answer and all task fields, is verified before revision. Only that ancestor or
the exact revision is accepted. Campaign preparation and restoration bind the
revised public request and judge before generation. Local inspection of all five
provider preparation paths excludes the exact private checker and reference
answer; it makes no API request or general disclosure guarantee.

## Independent target, SDK-dependent evolution

The state oracle checks all 64 complex density entries with absolute tolerance
`1e-10` and zero relative tolerance. The target vector has amplitudes `1/sqrt(3)`
at indices 1, 2 and 4. Its outer product therefore has `1/3` in the nine positions
whose row and column are both in `{1, 2, 4}`, and zero elsewhere. The checker
constructs those entries directly, without candidate equality or equivalence
methods. A coherent symmetric state passes up to an overall global phase;
incoherent populations alone are insufficient.

The checker separately expands and validates the measurement map, constructs a
preparation-only circuit from allowed operations, and asks the pinned SDK for its
density matrix. Gate unitarity is also checked at the same declared tolerance.
The [pinned DensityMatrix source](https://raw.githubusercontent.com/Qiskit/qiskit/2.4.2/qiskit/quantum_info/states/densitymatrix.py)
implements zero-state instruction evolution; the
[Initialize source](https://raw.githubusercontent.com/Qiskit/qiskit/2.4.2/qiskit/circuit/library/data_preparation/initializer.py)
uses reset followed by state preparation, so it is an allowed nonunitary
preparation instruction rather than a unitary Gate.
The independent target does not prove the SDK evolution or graph decoder correct.
Those dependencies still need independent qualification. No sampler executes,
and this condition does not test shot variability, hardware noise, transpilation
or execution on a quantum device.

Any correct construction is allowed, including the reference gate sequence,
direct amplitude preparation, a full Householder unitary, explicit composites
and initialization. A correct constant circuit is a legitimate answer to this
fixed no-argument problem. Constructor use, circuit minimality, native return
object provenance and sampling execution are explicitly unattested. Names,
labels and metadata are not scored, although transmitted data still has to fit
the public resource profile.

## Transport and evidence boundaries

The recipe freezes graph protocol 4, delta transport, individual calls, a 16 MiB
message/state limit, 100000 nodes/edges, 512 KiB array/matrix limits and graph depth
128. It uses the registered data-only Qiskit representation. No Python
deserialization or copied-value fallback is introduced by this revision. A
decoded QuantumCircuit category is not independent proof of the candidate's
actual native object identity or an honest candidate-side encoder.

The [source-bound host bundle](artifacts/task66-symmetric-w-2026-10-07/README.md)
predeclares 84 trusted authored controls: 32 semantically correct alternatives and
52 violations across both suites. Direct host judgments agree with all declared
outcomes. Graph transfer supports 82 controls: 30 pass and 52 fail with the same
judgments. Both Initialize controls pass the mathematical checker but fail
encoding with `Retained Python operation requires another component codec`.
They remain correct controls and release blockers; they are not excluded,
rescored as incorrect, or replaced with another preparation method.

The diagnostic labels encoder WireError separately from an oracle result.
Decoder, transaction and protocol errors abort verification rather than becoming
an unsupported-representation observation. The exact replay claim covers the
declared projection: node-kind counts, resource-bound booleans, verdicts and
diagnostics. Raw envelopes, autogenerated SDK names and UUIDs are not retained
or replay-bound. Both arena sides run on the same trusted host and share captured
public anchors; this is not independent process or candidate-encoder qualification.

Sixty-five independent vector global phases pass the density arithmetic oracle.
All 128 single real/imaginary entry perturbations are rejected. Additional circuit
controls cover wrong relative phases, controlled base phases, open controls,
measurement violations and generic definition limits. Review found and corrected
a nesting off-by-one, a controlled-definition limit bypass and an overly broad
transport-error classification. These finite tests do not exhaust all correct
circuits, floating-point behavior or adversarial encoders.

The isolated runner retains all 84 cases and freezes both judge manifests and
expectations before execution. Its test requires an explicit immutable image and
remains skipped while Docker is unavailable. Runtime/resource qualification,
encoder integrity and independent human contract/oracle admission are pending.
The judge and evidence remain release-ineligible. Host checks and AI review do
not qualify a headline model score or complete the 151-family overhaul.

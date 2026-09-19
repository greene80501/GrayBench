# Controlled-gate transport

The fixed `controlled_gate_v1` record supports exact Qiskit `ControlledGate` and
`MCXGate` instances. It preserves the internal name, label, control count/state,
base gate and raw cached definition, including supported nested definitions and
metadata. Circuit operand order is retained, including nonadjacent control qubits.

It does not invoke `.control()` or synthesize a replacement during decoding. A
fixed constructor initializes structural state, then the decoded base and cache
are assigned explicitly. ControlledGate's parameter setter delegates to the base
gate, so initialization uses a fixed empty placeholder to avoid changing the
submitted base parameters. The placeholder never survives in the reconstructed
object. Numerically or semantically incorrect custom definitions are retained for
the oracle instead of being replaced by a controlled version of the base gate.

Open controls are important: the public `definition` property wraps a closed gate
with X conjugations, while `_definition` stores the unwrapped cache. Encoding the
raw cache preserves lazy behavior and avoids double application of those X gates.
The internal name is stored separately from the computed open-control name suffix.

Exact classes and a fixed field schema are required. Extra state, inconsistent
open-control flags, missing bases, mismatched widths, recursive graphs beyond the
existing depth limit and oversized nested matrices are unsupported. The existing
512-qubit structural limit applies; MCX records require at least three controls
because Qiskit constructs different classes for one or two. Standard controlled
subclasses, annotated operations, alias identity and general control flow are not
newly admitted by this codec. Nested bases/definitions must each have a supported
representation. Aggregate matrix limits include both the base and its cache.

Installed Qiskit 2.4.2 source was inspected for ControlledGate parameter delegation,
construction and open-control definitions, plus MCX initialization. The
[IBM ControlledGate API reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.ControlledGate)
documents these concepts; its version is not represented as the pinned runtime.

Task 89 (two-control H), task 90 (custom controlled two-qubit gate) and task 147
(four-control Y containing MCX) retain their original upstream tests. Passing
references and identity controls only establish targeted compatibility; they do
not constitute complete task admission or certified model scores.

## Validation

Thirteen focused tests cover open-control states, names, raw caches, symbolic
base parameters, metadata, nonadjacent operands, malformed state, recursion and
shared matrix limits. The separate review agent passed these tests and found no
actionable issue, including additional renamed-MCX/custom-cache and Hamiltonian
base probes. The final Docker-enabled suite passed **436 tests**, zero failures,
errors or skips, in 185.54 seconds. Local artifact:
`outputs/GrayBench-v3-controlled-wire-tests.xml`. Ruff lint and all 83 formatting
checks passed.

Task 147 mutates its input circuit. The current alias-aware mutation bridge is
not implemented, so canonical task147 remains unsupported even after its gate
representation is transportable. A separately labeled copy-return probe isolates
the new controlled-gate representation; it does not establish full mutation or
public-contract admission. No model API generations were used.

[Protected replay](GrayBench-v3-controlled-wire-evidence.jsonl) contains 14
completed normal/hard cases with no pending attempt: task89/90 references pass
in both suites (four passes), six identity controls fail, task147 references are
unsupported at the alias-aware mutation boundary, and two copy-return probes pass.
These are targeted results, not an updated full-suite reference score.

Evidence SHA-256:
`f7f542384dc02a84f6baf250ce567a17cad897dc7f537af19b634f8759370764`.
The actual source bytes, task/completion records, runtime and protected transcripts
are retained. CRLF worktree source hashes can differ from Git-normalized blobs.

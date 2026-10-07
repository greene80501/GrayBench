# Task 122: external transpiler call without output comparison

Both pinned prompts ask for an EfficientSU2 circuit with the supplied qubit
count, circular entanglement and one repetition, transpiled through the IBM
service for `ibm_brisbane` with AI enabled and optimization level 3. The task
is already marked external-service-dependent in the inventory. The user has
chosen not to set up IBM Quantum for this phase.

Read-only Python 3.12 AST inspection of the content-pinned tests found the
same single assertion in normal and hard:
`isinstance(gen_transpiled_circuit, qiskit.circuit.QuantumCircuit)`. The
candidate result is read only by that assertion. Each test constructs a
`TranspilerService` and calls `transpiler_service.run(og_circuit)`, but the
assigned `expected_transpiled_circuit` is never read. The source itself notes
that a comparison was deferred pending a random-state/seed feature. Thus, if
the service call succeeds, the test has no assertion on the candidate's
qubit count, ansatz, entanglement, backend, AI setting, optimization level or
transpiled behavior. An empty `QuantumCircuit` would satisfy the only
candidate-result assertion; this is a source-level implication, **not** a
recorded live-service pass.

The pinned normal task digest is
`810a3ae07ca3dbabe1733bd57a1588b4ee2faa4acd683b30940ab11448340eb4`
and its test SHA-256 is
`87a4122a512b607d0e36a95b5fe4ac30a9ff64561945ff5941e9063dccddb5fd`.
The hard task digest is
`1d73d2ef3cda8bcf372dda39720146dedb4479fb4db96162c9e6f283cf60a94e`
and its test SHA-256 is
`6b52a693eda7bc8ed2e65731d3e0d973c234ad5f5457286834051e5ab8c6b3f8`.
Both are from the frozen dataset revisions in `engine/src/graybench/datasets.py`.
No service call or model generation was made in this audit.

A future versioned task needs a declared service-dependency policy and an
observable comparison that accepts valid transpiler alternatives rather than
requiring byte equality with a nondeterministic reference. An output
comparison alone cannot prove that the candidate actually invoked the
requested AI service; that requirement needs independent observation.
Service access and the oracle remain unqualified, so this task is
unadmitted and cannot silently count as a normal/hard offline pass or failure.

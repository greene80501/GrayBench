# Task 3 and task 26 contract review

This local review concerns the pinned normal and hard task variants. It does not
admit either task for publication and does not replace the upstream tests.

## Task 26: Bell-pair placement and an undisclosed measurement

Both public prompts ask for a three-qubit DAG circuit with a Bell state on qubits
0 and 1. Neither asks for a measurement or a particular gate count/depth. Both
upstream checks require depth 3 and exactly one H, one CX and one measurement.
They do not inspect the qubit operands or resulting quantum state.

The local authored contract probe constructs two ordinary Qiskit DAGs and evaluates
those four conditions without executing dataset code. The requested H(0), CX(0,1)
unmeasured circuit has depth 2 and therefore fails the conditions. H(1), CX(1,2),
measure(1,1) satisfies all four conditions but prepares the Bell pair on the wrong
qubits. Independent statevector equivalence checks distinguish the two placements.
This establishes a specification/test mismatch; it is not a protected benchmark
judgment, an LLM score, or an independent audit.

For a strengthened release, state explicitly whether measurements are permitted,
required or forbidden, and what returned-state semantics are required. Validate
qubit placement and Bell-state coherence before any allowed final measurements.
Do not require the reference's incidental register names, gate ordering, operation
count or depth unless the revised public contract actually requires them. An
upstream replication must retain and disclose the original checks.

## Task 3: drawing content and measurement scope

Both prompts request a measured three-qubit GHZ circuit, plus a Matplotlib drawing
of that circuit when drawing=True. The test checks that the final instruction is
a measurement, strips final measurements, checks the remaining GHZ state, and only
checks the drawing object's Figure type. It does not check drawing content or that
the drawing corresponds to the returned circuit.

The phrase "measure it" also leaves measurement coverage underspecified. The
reference measures all three qubits, but the test accepts any final measurement
that can be removed before the GHZ check. A strengthened release must clarify the
measurement contract before adding all-qubit requirements. A blank Figure is a
separate unambiguous defect: it is not a drawing of the circuit.

Faithful Figure transport and a meaningful visual/structural drawing oracle are
separate requirements. Reconstructing a blank Figure merely to satisfy isinstance
would hide the interface limitation and preserve the weak oracle; it is not an
acceptable route to task admission.

## Evidence scope

The pinned task records, authored probe source and local results are preserved in
outputs. Exact-upstream-test probes with known authored fixtures ran successfully in
an isolated diagnostic container, using the unchanged pinned tests. They deliberately place those trusted fixtures
and tests in one process, and must never become an execution path for LLM outputs.
The production candidate/judge separation remains unchanged.


## Exact test results

| Fixture | Normal | Hard | Contract finding |
|---|---|---|---|
| Task 3 reference | pass | pass | Positive control |
| Task 3 blank Figure | pass | pass | Wrong drawing accepted |
| Task 3 only qubit 0 measured | pass | pass | Measurement coverage needs clarification |
| Task 3 wrong GHZ state | fail | fail | Negative control |
| Task 26 reference | pass | pass | Positive control |
| Task 26 requested Bell pair, no measurement | fail | fail | Undisclosed measurement/depth requirement |
| Task 26 Bell pair on qubits 1 and 2, measured | pass | pass | Wrong pair accepted |

All 14 invocations completed without execution errors. These pass/fail labels
are what the upstream assertions did, not correctness claims about the fixtures.
The record contains the exact executed source and pinned task digest for each
fixture, the immutable image, engine source manifest and all results. It is a
local authored diagnostic rather than independent certification or an admissible
model-scoring path.

Evidence: `GrayBench-task3-26-exact-oracle-probe.json`, SHA-256
8f923fd81186ceb336005ad5d2a1032a2e67ab78f33a5489bc196647aaa9e0fe

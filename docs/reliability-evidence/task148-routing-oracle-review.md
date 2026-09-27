# Task 148: gate counts and connectivity do not preserve meaning

Both pinned prompts ask for SWAP routing of the supplied circuit under a
backend's coupling map without transforming the gates. Both tests generate
three random five-qubit circuits for FakeKyiv, use `CheckMap` to verify the
returned circuit's routing, then compare the multisets of operation names
after discarding SWAPs. They do not verify which logical wire each original
gate acts on, its parameters, or the routed circuit's logical action.

The [exact-test probe](task148_oracle_probe.py) ran six authored cases against
the unmodified normal and hard tests in the immutable Python 3.12.14 /
Qiskit 2.4.2 image with network disabled. The canonical `BasicSwap` reference
passed. A mutant first performed the same routing, then moved the first
one-qubit operation onto the next physical wire while retaining its operation
object. It passed both suites and recorded three actual wire changes in each
suite's three randomized calls. A deliberately added X gate failed the count
comparison in both suites. A second complete probe produced the same saved
observations.

For an independent semantic witness, the probe supplied a valid five-qubit
circuit containing only X on qubit 4. No routing SWAP is needed for that
input. The reference returned X on qubit 4 with the same operator; the mutant
returned X on qubit 0 with a different operator. This witness avoids treating
physical-operator equality as a general routing oracle, because a routed
circuit with inserted SWAPs may carry a changed output layout. The normal
`check` was invoked explicitly; the hard test invokes it itself. No IBM
account or model API request was made.

The [saved UTF-8 result](GrayBench-task148-exact-oracle-probe.json) has SHA-256
`4c63dd92416877fe3b05f4dbae39ae5dc0473eb022059b44c7aa7c7efe86b35a`.
It binds the source, dataset pins, task digests, candidate hashes, runtime,
six exact-test outcomes, mutation counts and fixed-input witnesses. This is
authored native diagnostic evidence, not a protected-judge run or benchmark
score.

A separately versioned semantic oracle should trace the logical-to-physical
mapping through inserted SWAPs, validate the preservation of original gate
operations and their parameters on the mapped logical wires, and check the
backend's directed coupling constraints. It should accept different valid
routes. Keep the historical upstream tests unchanged; task 148 is not
admitted for a verified score.

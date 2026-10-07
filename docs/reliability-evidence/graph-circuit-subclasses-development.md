# Fixed QFT and GraphState circuit subclasses

The persistent graph previously rejected these exact Qiskit circuit subclasses.
Flattening them to plain QuantumCircuit would erase their class and QFT's lazy
construction/invalidation behavior. A fixed optional selector now retains QFT or
GraphState under the quantum_circuit node kind. Plain circuit records retain their
existing schema. The instruction registry also admits exact GraphStateGate.

QFT's pinned raw blueprint fields are retained with the actual dictionary, native
CircuitData, builder scope and child aliases. Capture does not call data, build,
constructors or class property setters. Cache invalidation can replace native
storage while detached references continue to identify the old storage. Raw
adjacency matrices remain separate from an already cached graph-state definition.
No automatic resynthesis repairs inconsistent mutable candidate state.

Class selectors come from a fixed registry, never payload imports. Unknown classes,
extra fields, invalid flag types and class changes are rejected before live
mutation. This supports the pinned exact classes, not arbitrary Python subclasses.
General history/performance and SDK resource policies remain admission work.

Five initial local cases failed as unsupported before implementation. The focused
suite subsequently passed 26 tests in 21.41 seconds, including four protected
snapshot/delta QFT controls. Incorrect swap settings remain assertion failures.
The full Docker-enabled regression suite passed 998 tests in 452.44 seconds, with zero failures, errors or skips. Its preserved JUnit record is GrayBench-v4-circuit-subclass-tests.xml.
Ruff lint and formatting passed for 142 files. Independent read-only review found
no blocker; separate narrow probes covered empty and inverse QFTs, uncached
GraphState, operator equivalence, lazy flags, return identity and arbitrary
subclass rejection. That reviewer did not run Docker or the full suite.

## Reference evidence

All six selected tasks (78, 101, 145 in normal and hard) changed from unsupported
to pass. Complete chains, task selections/identities, canonical completion hashes,
extraction/public digests and judge manifest identities were verified. The final
source manifest matches the tested full-suite checkout. Only graph_instruction.py
and graph_quantum_circuit.py differ from the baseline. An intermediate after run
preceded Ruff import ordering; its evidence is retained separately.

| Raw artifact | SHA256 |
|---|---|
| GrayBench-v4-circuit-subclasses-before.jsonl | 58f69d44af1f6410a02d9725b494aadc2567d59ccf47aa906f71c6f5e23983c9 |
| GrayBench-v4-circuit-subclasses-after.jsonl | be245065d503abb1a73653f1ee87d2223a453fcdf4615f298f3c491d6cc144cb |
| GrayBench-v4-circuit-subclasses-after-final.jsonl | 4233593db0f4fe1f5ff98b030a13d5cb4d34f65fbfa3e58c9c4c4fd248130007 |

The summary stores verified chain heads. The probe and comparison script use
workspace-relative dataset/output paths from engine/ and require fresh output
filenames. Concurrent diagnostic work means these timings are not isolated
performance measurements. These are compatibility results, not model scores,
oracle admission, or replacements for the historical complete cohort.

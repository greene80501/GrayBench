# Control-flow graph development

Native Qiskit copies branch CircuitData when inserting IfElseOp. Reading the
native parameter cache returns fresh QuantumCircuit wrappers and membership
caches. Python leaf operations inside those branch snapshots can nevertheless
remain shared with the original branches and with separately held objects.

The implementation therefore represents native branches as intrinsic membership,
register, phase and operation values. It assigns no graph IDs to their fresh
wrappers. Retained leaf operations still reference the surrounding persistent
graph. Original IfElseOp dictionaries, conditions and branches use ordinary graph
references. The cached condition is independently read through a fixed native
conversion; changing the Python condition does not overwrite that cached value.

Compiled control-flow instructions also have fresh operation wrappers. A fixed
native conversion preserves that behavior during reconstruction. Native branch
operation trees share a 4096-operation budget, with a depth ceiling of sixteen;
matrix storage is summed recursively into the existing graph budgets. These
bounds remain explicit development capabilities, subject to the uniform resource
audit. They are not tuned to particular task answers.

Nine new tests cover original/cached branch divergence, shared Python leaves,
nested compiled branches, bit and register conditions, malformed nested data,
sibling operation limits, updates to previously exported circuits with ordinary
and singleton gates, and a native/protected execution comparison. The initial
full run passed 870 tests in 388.63 seconds with no failures, errors or skips, but
the reference replay then exposed a missing update case. That result predates the
two corrections below. The final Docker-enabled suite passes 872 tests in 348.98
seconds; its separate JUnit report confirms zero failures, errors or skips.

The first eight-case reference replay passed six cases and reported task72 as
candidate_error in both suites with an unbound owner-cache diagnostic. Native
conversion's default operation copying broke retained leaf identity. Disabling
copying fixed a new ordinary-gate regression but the second replay still failed
task72: conversion also discarded singleton wrappers inside branches. Preserving
the original intrinsic branch parameters after conversion fixed the corresponding
private-anchor regression. Both failed replay files remain preserved as evidence
of transport defects, not model capability measurements.

The third source-guarded replay passes tasks51/72/88/121 in both normal and hard
suites. `GrayBench-v4-ifelse-reference-verified.jsonl` has SHA256
`fbc13e2b4399ce5856f2737af302a7d76558e38d051b19969879c965db840536`
and chain head `3af01f71adf0ebf7af239ba0a2ed20eb1ee455a3f49d8fa64a591453b4d5b519`.
The earlier files are `GrayBench-v4-ifelse-reference.jsonl` (SHA256
`76ffa0187a52be256ee4ec16e735f64928242ac683d71ff9064b17d5a0b76121`)
and `GrayBench-v4-ifelse-reference-fixed.jsonl` (SHA256
`264b5dbfe0b6fe3d80f6e72760d3044521b89fddb42b44e965637649fbf4d7e0`).
The overloaded WireError-to-candidate_error classification at the trusted graph
boundary remains an audit item: internal reconstruction defects must be separated
from invalid candidate payloads before release.

Classical expression conditions and loop instructions remain required work.
This increment does not certify complete control-flow support, oracle admission
or a model score.

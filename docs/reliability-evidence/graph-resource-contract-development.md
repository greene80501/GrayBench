# Graph resource contract development

The configured output_limit previously reached the host but not either graph
arena: both silently used GraphLimits() with a 1 MiB message ceiling. The trusted
response reader also had a separate hardcoded1 MiB ceiling. A protected1.1 MB
message under an explicit 4 MiB configuration reproduced unsupported first, then
infrastructure_error after only the arena fix, and finally pass after the reader
used the same declared budget.

GraphLimits now lives in an SDK-independent module. The complete six-field record
is frozen into the private task payload and judge manifest, passed to the
candidate config, and validated by both runtimes. The existing import from
graph_wire remains compatible. Cumulative output accounting includes bootstrap
messages and is named explicitly in the manifest; the whole message envelope
still counts against the process output budget. Defaults remain unchanged.

Eight new tests cover manifest/payload binding, actual protected large-message
acceptance at 4 MiB and rejection at the1 MiB default, malformed records and a fresh
host interpreter that imports neither NumPy nor Qiskit. Together with three
protocol tests, 11 focused checks pass. Full Docker regression passed 922 tests in 362.89 seconds with zero failures,
errors or skips; Ruff lint/format 135 files passed. Report:
GrayBench-v4-resource-contract-tests.xml. The source-bound before/after probe uses
identical task/completion identities and settings; it changes from unsupported
to pass at 4 MiB. Both complete chains were independently verified, and the after
manifest exactly matched current runtime bytes.

Raw before: GrayBench-v4-resource-contract-before.jsonl, SHA256
04c97d41388c6e7b1ffab4aad884aca8953fd9d9f77b2bb67cd7c0cc1737dfd1.
Raw after: GrayBench-v4-resource-contract-after.jsonl, SHA256
cb84e9dff6ae15b3412dd46af7927083738168b5b7fa03f9abe223c0c07b904b.
These are controlled resource fixtures, not model measurements.

This fixes propagation of an already exposed configuration value. It does not
calibrate or raise production defaults, solve task100's packed-operation ceiling,
or prove task109 fits a chosen budget. Per-codec intrinsic limits and cumulative
versus per-message resource accounting remain part of the broader audit. No
reference/model scores are changed or silently recomputed.


## Cumulative transport finding

Task 109 requests 1000 candidate calls. The full 38db7fa scan records its budget
failure at call 27, not a single oversized circuit. Successful candidate graph
responses contain 39 nodes on call 1, 201 on call 10, 381 on call 20 and 489 on call 26.
JSON serialization estimates grow from 6201 to 73551 bytes over those calls.
GraphArena.snapshot explicitly revisits every exported object to preserve detached
aliases, and the host output counter accumulates across calls. A larger individual
message limit alone does not address this growth.

Next profile repeated-call behavior and review bounded incremental transport and
reconstruction, preserving detached aliases and atomic validation. Any protocol
change needs its own malformed-frame, stale-state, mutation and identity tests.
Task 100 separately uses randomized Solovay-Kitaev decomposition and reaches the
4096packed-operation budget. Both resource calibration and judge-input randomness
need explicit frozen policies; neither should be tuned to individual model answers.

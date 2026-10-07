# Task109 normal and hard: complete protected reference diagnostics

The unchanged hard canonical solution and upstream test completed all 1,000 calls
using protocol4 delta-v1 on runtime0379d13. The isolated checkout remained frozen
through completion, and its source manifest was checked against the stored header.
This is reference interface calibration, not a model score or oracle admission.

The run explicitly allowed 16 MiB wire/state capacities and separate 3,600-second
candidate and judge budgets. These diagnostic ceilings are not default promotion
or a calibrated production policy. No calls or retained object history were dropped.

- Result: pass; 1,000 recorded calls and 2,000 graph frames.
- Graph frame bytes: 4,053,875; final retained state: 18,021 nodes / 2,459,246 bytes.
- Candidate active time: 1,348.516 seconds; judge wait: 1,290.488 seconds;
  wall time: 2,640.546 seconds. Active time includes bridge work, not just user code.
- Other diagnostics ran concurrently; these are observed timings, not isolated
  performance measurements or a basis for provider/model budgets.

The data-only auditor verifies event/transcript hashes, manifest digest,
bidirectional delta bases and full reconstructed-state hashes, session/sequence
and declared node/state/frame bounds. It does not execute SDK objects or prove
semantic transport equivalence. Its six malformed-evidence controls are preserved
alongside the auditor.

The normal counterpart also completed all 1,000 calls and 2,000 frames. Its
frozen runtime source manifest matches the stored header. Data-only audit found
4,053,919 graph-frame bytes and a final retained state of 18,021 nodes /
2,459,290 bytes. Candidate active time was 1,523.940 seconds, judge wait
1,444.482 seconds, and wall time 2,969.890 seconds, with the same concurrency
and calibration limitations described above.

Normal raw: GrayBench-v4-task109-full-delta-normal-0379d13.jsonl.
SHA256: bb9b262c848ce7b59b45c57b369f4ff7d69924c4fe5c363cfc6101109710cef6.
Chain: 2c20caa4b4da2b9a6b806a6fe90c95a5097767b1efdf392edf49c1f9bd8c706f.
Summary: GrayBench-v4-task109-full-delta-normal-0379d13-audit.json.
Reproducer: task109_full_delta_normal.py.

Raw: GrayBench-v4-task109-full-delta-hard-0379d13.jsonl.
SHA256: 37d91eb19dd00adb4ace7743eba907af748a3f00d2610a2c292cef7bb31750c4.
Chain: da6d45fa0481a0c399cce5e0c22cf2a9a19073248b71de3a99eb9da124f90150.
Summary: GrayBench-v4-task109-full-delta-hard-audit.json.
Reproducer: task109_full_delta.py, run from engine/ with its workspace-relative
cache and a fresh output path. Auditor: audit_delta_transcript.py INPUT [NEW_OUTPUT].

The previously documented false accepts and ambiguous parameter-domain/resource
contract remain unresolved. See task109-oracle-review.md and
task109-parameterization-contract.md. This result is not added to the historical
286-case aggregate and does not establish benchmark certification.

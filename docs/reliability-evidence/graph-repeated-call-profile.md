# Repeated-call graph profile and optimization requirements

This is diagnostic evidence for runtime 46b7487, not a model score, protected
execution timing, or proof that an incremental protocol is correct. The captured
source manifest matches the local runtime, and the probe hash and row totals were
independently checked before preservation. Python 3.12.14 and Qiskit 2.4.2 were used.

## Reproducer and preserved evidence

`profile_graph_roundtrips.py` creates two anchored GraphArena instances in one
process. Each of 100 calls returns a new one-qubit circuit with H and a
parameterized RZ. The receiver binds its parameter in place before the next call.
All previously exported objects remain retained. The per-message limit is 16 MiB
for this diagnostic, not a production-default change. The script asserts the
runtime source manifest is unchanged during execution.

The original invocation, from `engine`, was:

```text
uv run --extra qiskit --extra dataset python ../../../work/profile_graph_roundtrips.py
```

The preserved script retains its original exclusive output path. Replaying it
requires a fresh output location; do not overwrite the historical artifact.

- Result: `GrayBench-native-graph-profile-46b7487.json`
- Result SHA256: `cd6c7540281f4d1dc523446c67fafd3a0358119309aefa956ad09844a5cfdeff`
- Probe SHA256: `26de4952f9f864b40c3f8b65e05e1a7d43b6cac4ec1b4e0f18f8e50113ced91c`

The result and probe are stored without Git newline normalization to preserve
their byte identities. The result contains the runtime file manifest.

## Measurements

The run took 18.0958 seconds and serialized 24,503,549 graph bytes. Comparing each
record against the last transmitted complete table yielded 302,367 changed-record
bytes (1.23% of total graph bytes). That estimate excludes any delta framing,
roots, hashes, validation metadata and acknowledgment overhead. It is not an
implemented protocol or a claimed compression ratio for production traffic.

| Stage, summed across 100 calls | Seconds |
| --- | ---: |
| Judge snapshot | 1.7129 |
| Candidate prepare | 4.1604 |
| Candidate commit | 2.4404 |
| Candidate snapshot | 1.7660 |
| Judge prepare | 4.2751 |
| Judge commit | 2.5396 |

Preparation and commit total 13.4155 seconds. At call 100, forward/backward frames
contain 1804/1821 nodes and 240700/243166 bytes, while only 2/17 records changed.
These observations establish growing redundant transmission and reconstruction
work. They do not establish a precise asymptotic bound or predict Docker timing.
There are no pipes, separate processes, JSON envelopes or container startups in
this probe. Both arenas share the captured public-anchor registry in this local
diagnostic; a protected replay is required before performance acceptance.

## Required semantics for the next implementation

The reference workload for task 109 invokes the candidate 1000 times. Neither
reducing those calls nor increasing the cumulative byte budget alone addresses
the observed implementation overhead fairly. Both transport and reconstruction
must be measured after changes, with unchanged candidate code and test inputs.

An incremental wire representation must have an explicit version and frozen
configuration identity. It must bind each frame to its session, direction,
sequence and exact prior accepted state; validate the reconstructed complete
table; reject stale bases, missing records, duplicates, invalid ownership and
dangling references; and advance the accepted base only after successful commit.
Transport-byte limits and reconstructed-state limits must be distinct, explicit
and bounded. A small patch must not bypass the complete-graph capacity limits.

An optimization of private reconstruction must preserve these existing checks:

1. `prepare_anchors` captures actual current live objects, including local-only
   supplemental children. `_records` alone is not a live-state baseline.
2. Immutable state, codec transitions, owner/cache binding and native canonical
   reconstruction are validated privately before any live application.
3. `commit_anchors` rechecks state and exact object identities after preparation.
   A mutation or equal-but-distinct child replacement in that interval must fail.
4. Exported detached aliases remain observable across calls. Root reachability
   alone is not a safe deletion criterion; neither is a guessed Python refcount.
5. Cycles, reverse dependencies, shared mutable anchors, native owned caches and
   shared array storage must participate in any proposed affected-region analysis.
   A shared singleton must not be treated as immutable without codec evidence.
6. Failed live application closes the arena. Recovery must not continue from an
   uncertain partially applied state.

Wire deltas can be developed independently, but must not be presented as solving
task 109 while full-history serialization or rehearsal remains the bottleneck.
Scoped reconstruction is not approved by this evidence: its dependency closure
and isolation properties still need a concrete implementation and adversarial
tests. No object lifecycle or garbage-collection shortcut is justified here.

## Acceptance evidence still required

Use both full snapshots and the proposed implementation on identical deterministic
fixtures, checking return values, mutation propagation and held alias identity
after each step. Include changes to previously exported objects absent from the
current roots, cycles, owner cache replacement, equal-but-distinct substitutions,
malformed frames, stale prepared transactions and injected reconstruction failure.
Protect these tests with actual separate candidate/judge containers as well as
local unit tests. Preserve before/after source manifests and raw results.

Repeat the 100-call diagnostic and the complete 1000-call task workload. Record
actual envelope bytes, stage timings, peak retained state and final outcome.
Freeze resource policy across models before collecting comparisons; never choose
limits from an individual model's answer. The existing 922-test pass and 286-case
calibration remain historical evidence, not acceptance of an unimplemented change.

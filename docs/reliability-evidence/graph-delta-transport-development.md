# Incremental graph transport development

The opt-in `upstream-graph-delta-v1` campaign recipe uses the same protocol4
protected judge and graph semantics with a new `call_graph_delta_v1` frame.
`upstream-graph-v4` continues to select full snapshots. Neither recipe is a
certified benchmark. The explicit recipe refuses an override to another
transport or protocol, and restoring a campaign retains its selected transport.
Model requests are unchanged; judge configuration identities differ.

For controlled reference/probe runs, the Python API is:

```python
from graybench.upstream import UpstreamJudge

judge = UpstreamJudge(
    image=immutable_image,
    protocol=4,
    graph_transport="delta-v1",
    output_limit=1048576,
    graph_state_limit=4194304,
)
```

`graph_state_limit` defaults to `output_limit`; it does not silently increase
capacity. The frozen `graph_transport` record names the mode, `wire_bytes` and
`state_bytes`. The graph limit record's `message_bytes` bounds the reconstructed
full graph, while the frame and trusted response reader use `wire_bytes`.
Cumulative host output accounting, bootstrap costs and envelope accounting are
unchanged. Different wire/state bounds are rejected in snapshot mode to prevent
an ineffective configuration. Graph settings are rejected for protocol3.

## Frame and transaction contract

Every frame contains format, session, sequence, anchors, roots, sender side,
previous-state digest, resulting-state digest and changed node records. On the
first frame only, the previous digest is null. All later frames bind to the
last locally emitted or successfully committed snapshot, across both directions.
The result hash is SHA256 of the full canonical JSON snapshot, with records
sorted by ID. JSON is ASCII escaped, finite-number-only, sorted by key and uses
compact separators, matching `wire_bytes`.

The receiver copies the retained data records, overlays unique changed records,
checks total node/state bounds and the resulting hash, then invokes the existing
GraphArena preparation on the reconstructed full snapshot. The unchanged checks
still enforce owner IDs, anchors, codec schemas, immutable transitions, references,
native cache reconstruction, live-state baselines and private rehearsal. Hashes
bind state; they do not authenticate the candidate or establish correctness.
Candidate-controlled frames with valid hashes still undergo all semantic checks.

The incoming base advances only after successful graph commit. Prepared frames
carry a private owner and generation, and immutable serialized snapshot bytes;
the expanded snapshot exposed for call-root validation is a defensive copy.
Foreign, stale or replayed preparations are rejected. Commit failure closes the
session. Outbound encoding failure also closes it because the underlying snapshot
may already have allocated IDs. The enclosing protected bridge must terminate
after uncertain delivery; there is no automatic retry or base reset.

No deletion operation exists. Previously exported objects, including detached
aliases, remain part of the reconstructed table and resource accounting. Roots
are always transmitted. Candidate exception roots and argument-root identity
are validated against the expanded graph before live commit.

## Verification and limits

The initial 12 tests failed because the delta implementation was absent. After
implementation they passed. Seven configuration/integration tests then failed
because the host did not expose transport selection; the campaign restoration
test failed because its explicit recipe did not exist. The focused suite now
passes 43 tests with Docker enabled, including:

- Cross-call detached aliases and cycles with unchanged records omitted.
- Wrong base/result hashes, direction, session, boolean sequence, duplicate and
  missing records rejected without mutation or consuming the valid next frame.
- Correctly rehashed invalid local IDs, dangling references, unknown kinds and
  invalid public anchors rejected by graph validation.
- Independent prepared payloads, replay/foreign rejection, live mutation between
  preparation and commit, and fatal outbound wire overflow.
- Expanded-state limits enforced even when the incremental frame is small.
- Protected identity positive/negative controls, singleton circuit caches,
  mutation before a caught exception and a following call.
- A spoofed response remains a candidate error even if the private test catches
  every exception; it cannot produce a pass.
- A 61-call protected fixture propagates mutations to retained state within the
  unchanged 1 MiB cumulative output budget.

All **954 Docker-enabled tests passed in 387.41 seconds**, with zero failures,
errors or skips in `GrayBench-v4-delta-transport-tests.xml`. Ruff lint and format
checks pass for all 138 engine/test files. These are development regression
checks; they do not establish complete benchmark admission.

A separate read-only code review found no blocking correctness or security issue
in the delta implementation and its integration. It did not independently rerun
the complete Docker suite. It recommended direct wrapper-level controls for an
injected underlying live-commit failure and an equal-but-distinct child replacement
between preparation and commit. Underlying graph tests already cover these kinds
of failures; retain these additional wrapper controls when changing reconstruction.

## Preserved comparison evidence

`delta_transport_probe.py` runs identical code and assertions with an unchanged
1 MiB cumulative budget. Full snapshots end with `infrastructure_error` and
`judge exited or exceeded output` after 47 recorded calls. Delta mode completes
all 61 calls with `pass`. Both complete event chains, matching case identities
and selections, and exact runtime source manifests were independently checked.
The snapshot failure remains an infrastructure outcome; it is not recast as a
model failure or erased.

| Artifact | SHA256 |
| --- | --- |
| GrayBench-v4-transport-snapshot.jsonl | bebd0ab49c3666546bbbf3685b0e1754fcb4578e3c55f9811e6e97d767dc14e5 |
| GrayBench-v4-transport-delta.jsonl | 78916ca59432587820ab8f959c91f3f9bf78afba2df91dc9281e5e784b5b6e0d |
| delta_transport_probe.py | 5a97a246163dd7066a934d48434374781f05a4ccee81ea3dd0d9469b71dc8aa7 |

The complete chain heads are respectively
`fb5b6795961fa9783143ac856bd9f4fe9c16024e922ad57ee6a0043c2f2016aa` and
`91dda39e284e662d6fdcf54e0cbe89e7139589b3fa867cd41a689320559ddb61`.

`profile_graph_transport.py` repeats the 100-call circuit workload separately
in each mode against the same unchanged source, with explicit 16 MiB wire/state
ceilings. It measures actual serialized graph frames, including delta headers,
but excludes outer protocol envelopes, pipes and Docker. These local arenas
share a process and public-anchor registry. There is only one timing observation
per mode, without control of other machine load; do not infer a precise speed
ratio or protected runtime from it.

| Mode | Total graph frame bytes | Wall seconds | Prepare + commit seconds |
| --- | ---: | ---: | ---: |
| snapshot-v1 | 24,501,949 | 18.3406 | 14.1417 |
| delta-v1 | 397,729 | 22.2663 | 16.2632 |

Delta mode sends 98.38% fewer graph bytes in this workload, but the observed local
runtime is slower. The result rejects any claim that wire deltas alone solve
task109. Full capture, reconstruction and added table/hash work remain measured
costs requiring further implementation.

| Artifact | SHA256 |
| --- | --- |
| GrayBench-native-transport-snapshot.json | 0a4c36daf06bbfaeae3197e321eaaedb19e93a910ea6f1b0c21cc20bc3b1ff3b |
| GrayBench-native-transport-delta.json | 3d9e5eeabbb550b20190c7d51bfc14d7e318674c976bdfc17753462a15ab70e2 |
| profile_graph_transport.py | 89e8d57451971ef8c349715ddaa165fb9af2f5fadf230e008f140b8cc0588089 |

Both JSON results contain the probe hash, source manifest and all 100 stage-timing
rows. Their hashes, probe bytes, row counts, byte totals and source identities were
checked before byte-identical preservation. The probes take explicit output paths
and refuse existing files; use fresh paths when reproducing. Run from `engine`
with `uv run --extra qiskit --extra dataset python`, the preserved probe path,
the mode (`snapshot-v1` or `delta-v1`) and a fresh output path. The protected probe
also requires the recorded immutable Docker image and its configured Docker path.

This implementation intentionally still captures and reconstructs full history.
It therefore addresses redundant wire traffic only. It adds hashing and data-table
work, which must be measured rather than assumed free. Scoped reconstruction,
the complete task109 workload, peak state accounting, full normal/hard transport
admission and uniform resource calibration remain required. The historical
286-case calibration is not replaced or combined with focused passing fixtures.

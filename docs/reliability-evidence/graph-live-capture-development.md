# Live capture validation and failure classification

The 6182a34 repeated-call profile prompted a closer attribution of capture and
reconstruction costs. This increment removes redundant work on the commit path
and fixes a protected-judge failure classification. It does not introduce cached
live state, selective reconstruction or object deletion.

## Identified scoring defect

A controlled trusted-test hook changes the judge's held list after graph
preparation but before commit. The candidate only returns its argument. Both
snapshot and delta modes previously reported `candidate_error`, even though the
change occurred entirely inside the trusted judge. Appending an unsupported
object during this interval was also classified as a candidate error. All four
new protected controls initially failed with those outcomes.

These failures now raise `GraphReconstructionError` and reach the existing
`infrastructure_error` handler. They block scoring even when the test catches
every exception. A recapture failure retains its underlying exception type and
bounded diagnostic. Malformed candidate frames still follow their existing
candidate-error validation path; no candidate payload is decoded by this guard.

## Reusing validated capture bytes

Preparation captures the full actual live closure and validates its complete
record table and depth, as before. It now retains the capture's immutable canonical
bytes instead of encoding that baseline again at commit. Private rehearsal is
unchanged.

Commit independently recaptures the complete actual live closure. Node, edge and
byte bounds remain enforced during capture. Before applying any state, it compares
the new canonical bytes with the validated baseline and checks the identity of
every captured object. Byte equality proves the second table has the same schema,
references and depth, so running schema/depth validation on it again adds no check.
Unequal captures are rejected, not validated into a replacement baseline.

Identity is a separate requirement: an unexported local child can be replaced by
an equal object and receive the same supplemental `b:` token, producing identical
bytes. The explicit identity comparison rejects this. No exported or supplemental
object is discarded to improve timings. Failed live application still closes both
the graph arena and its delta wrapper.

## Evidence and verification

Instrumented attribution is preserved in
`GrayBench-capture-profile-summary-6182a34.json` and
`GrayBench-delta-instrumented-6182a34.json`. The latter retains the original source
manifest and probe hash. Its SHA256 is
`a233ca2c7659138886f576f290cba5a7515b5036e93372295503c0334700067e`.
The local raw profiler dump has SHA256
`9b349f3ba099978daf50c213c6cf2a436d0abdbf541cdf246d1d3776704a954c`;
the summary records its invocation and top graph functions in data-only JSON.

The instrumented 100-call run made 400 `capture_bound` calls (14.925 cumulative
seconds) and 800 `_validate_records` calls (7.184 cumulative seconds).
`execute_owned` took 9.331 cumulative seconds across 600 calls. Cumulative times
overlap for nested functions and must not be summed. Profiling materially increases
runtime: its 47.94-second wall result is not comparable with the uninstrumented
22.27-second delta observation.

Thirty focused checks passed with Docker enabled after the fix. New controls also
cover equal-but-distinct supplemental children and closure after an injected
partial live update, addressing the preceding delta review's additional coverage
recommendations. The full Docker-enabled suite completed with **960 passed in
398.45 seconds**, zero failures, errors or skips. JUnit artifact:
`GrayBench-v4-live-capture-tests.xml` (398.431 recorded seconds). Ruff lint and
format checks passed for all139 engine/test files.

The four-case source-guarded before/after classification probe is complete. All
four before outcomes are `candidate_error`; all four after outcomes are
`infrastructure_error`. Complete event chains, identical task/code identities and
selections, and the after runtime manifest were independently verified. Timing
fields are observations, not performance comparisons: the fault probes ran while
the independent regression suite was active.

| Artifact | SHA256 |
| --- | --- |
| GrayBench-v4-live-capture-before.jsonl | 5c49d583b44977e68b97cc75c432533f8cae0f4e8d9d55db41bc227404994b69 |
| GrayBench-v4-live-capture-after.jsonl | d35c71923af4119cff279fb0c6ba819a52ec1e51c499e0645d6b87fe3050d204 |
| live_capture_probe.py | 5cbb63bbaa7b48afb087688edcdaabf307e00352cd8feb5897bffda1699cb943 |

The before/after chain heads are
`37dbea945036cc08184b2fecc90bac41a57416aa7c84575ce4f440d999d6bf94` and
`8c64b50e0d6b438bd2ae18097ec71bd9b89e5a20272ff087d8f92b288775792e`.
The probe takes a fresh output path and refuses to overwrite existing evidence.
It uses the pinned image and Docker path recorded in the preserved script.

## Measured effect

The unchanged `profile_graph_transport.py` probe (SHA256
`89e8d57451971ef8c349715ddaa165fb9af2f5fadf230e008f140b8cc0588089`) was rerun
after the regression suite finished. Exact source identities, all100 rows and
byte totals were verified before preservation.

| Uninstrumented delta workload | Previous6182a34 | After |
| --- | ---: | ---: |
| Calls | 100 | 100 |
| Graph frame bytes | 397,729 | 397,729 |
| Wall seconds | 22.2663 | 19.6324 |
| Prepare + commit seconds | 16.2632 | 13.8277 |

The before observation is the preserved `GrayBench-native-transport-delta.json`.
The after observation is `GrayBench-native-capture-delta.json`, SHA256
`b962e22d1f08bc7299125b3e05b4cdb725ed8e2b1f1d1e897de0b1945ed3e66c`.
These are single local observations, with no control of other machine load,
sharing a process and anchor registry and excluding containers, pipes and outer
envelopes. They show a lower observed time, not a statistically established speedup
or protected1000-call acceptance.

The second instrumented run independently confirms400 `capture_bound` calls
remain while `_validate_records` and `_check_depth` fall from800 to600 calls each.
All600 `execute_owned` calls remain. The optimization removes redundant validation,
not live capture or native reconstruction. Its data-only attribution is preserved
in `GrayBench-capture-profile-summary-after.json`; instrumented result
`GrayBench-capture-instrumented-after.json` has SHA256
`1288bc592d1cccfa1705a2d3b85dac33f665d35ed5283f9afc8ea0fb36aa6267`.
The local raw profiler dump has SHA256
`74ea5ba74638fda294bb3414e454017a2114abe7b957fc10a74677454f8ea769`.
Do not compare its44.31-second wall time against uninstrumented timings.

An independent read-only review found no actionable correctness issue, conditional
on full-suite verification. It confirmed complete recapture, retained identity
checks, unchanged private rehearsal and the infrastructure-error path. It did not
certify profiling artifacts, task109 performance or release readiness. The existing
interval between capture and application is not a general atomicity guarantee for
arbitrary concurrent mutation; this increment does not claim to solve that issue.

Full-history traversal and reconstruction remain necessary implementation work,
as do the complete 1000-call workload, uniform budgets and whole-suite admission.
This is a development increment, not a new model score or release certification.

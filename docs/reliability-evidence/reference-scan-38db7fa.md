# Complete reference scan at 38db7fa

This is source-guarded interface calibration, not model scoring or release
certification. All 286 planned offline cases finished. Eight external-service
families remain explicit exclusions in each suite; the full catalog still has
151 normal and 151 hard tasks.

| Suite | Pass | Unsupported | Fail | Infrastructure error |
|---|---:|---:|---:|---:|
| Normal | 113 | 28 | 1 | 1 |
| Hard | 113 | 28 | 1 | 1 |

The earlier full scan at 3ed07d2 had 80 pass, 62 unsupported and one infrastructure
error per suite. Task identities and selection are exactly equal. Each suite has
33 unsupported-to-pass changes and one unsupported-to-fail change (task63).
No previously passing reference regressed. The 68 individual transitions and all
60 unresolved outcomes are retained in GrayBench-v4-reference-summary-38db7fa.json.
Targeted results were not added to a previous aggregate.

## Evidence

Raw: GrayBench-v4-full-reference-38db7fa.jsonl.
SHA256: d1b401f97af2d2945ec37573d8b6ed414d5e313f9c0567be49f17047647f0254.
Chain head: dcdce3542fe5503e5cae4886287c6958aaebc5b359d85f03ad84e0e416d10f92.
The complete chain and planned/result identities were independently inspected.
The captured source manifest exactly matched runtime bytes after completion.
The source was unchanged during the scan. The same implementation passed all
914 Docker-enabled regression tests; all eight GitHub CI checks passed.

## Remaining work

The unsupported task IDs are 3,26,27,28,29,30,34,35,76,78,90,91,100,101,109,
112,114,115,116,119,120,123,124,125,135,145,148,149 in each suite. Their exact
diagnostics are preserved in the summary. Missing interfaces include figures,
DAGs, local runtime jobs, custom passes, circuit subclasses, instruction fields,
backend/noise/target/coupling components and external array buffers. Task100 reaches
the packed-operation limit; task109 reaches the wire-output limit. Resource-policy
calibration must be explicit and uniform, not raised selectively for one answer.

Task63 now reaches its private assertion and fails. Its oracle seeds NumPy in the
judge, while the reference draws its receiver basis in the separate candidate
process. The legacy shared-process assumption requires an explicit reviewed
condition or semantic revision; private oracle state must not be silently copied
into the candidate. This scan preserves the actual failure without rerolling it.

Task82 still expects bell.qpy in the judge's working directory. The existing
isolated task82-file-semantic-v1 recipe is a separate declared condition, not an
implicit fallback for upstream-graph-v4. The missing-file infrastructure outcome
remains recorded in this exact-upstream scan.

The DAG investigation also found that naive native-state reconstruction changes
future node IDs after some removal histories. See graph-dag-investigation.md.
Passing today's public checks alone is insufficient to validate those semantics.

Next resolve the remaining interface and resource-policy defects, and version
oracle changes explicitly. Complete oracle/task-contract audit, provider
calibration, reproduction and independent release review remain mandatory.
Neither this improved calibration coverage nor the green regression suite proves
the full benchmark is ready for model ranking.

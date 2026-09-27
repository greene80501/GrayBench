# Complete offline reference calibration at 77f29ff

This is a fresh source-guarded replay of the pinned canonical Qiskit HumanEval
normal and hard solutions. It is **interface calibration, not model scoring or
release admission**. The run used the unchanged pinned Python 3.12 image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`,
protocol 4, snapshot transport and the default 1 MiB wire/output ceiling.
The newer judge manifest states the graph limits explicitly; the earlier
source used the same default 1 MiB message, 512 KiB array/matrix and other
graph limits but did not record them in the manifest.

All 286 planned offline cases completed. The eight external-service families
per suite remain the same explicit exclusions. The previous and current task
digests, public contracts, canonical completion hashes, extraction hashes,
image, protocol, timeouts and output ceilings match. No prior reference pass
regressed. The 15 changed engine files and every verdict transition are in the
[machine-readable comparison](GrayBench-v4-reference-summary-77f29ff.json)
(SHA256 `fb94a6cb9f55df7e9ff20138e91df85c697162b2f7a884566e05f16326188128`).
The comparison verified both append-only chains and that the new header's
source manifest matches the current checkout.

| Suite | Pass observed | Unsupported | Fail observed | Infrastructure error |
| --- | ---: | ---: | ---: | ---: |
| Normal, earlier 38db7fa | 113 | 28 | 1 | 1 |
| Normal, current 77f29ff | 122 | 19 | 1 | 1 |
| Hard, earlier 38db7fa | 113 | 28 | 1 | 1 |
| Hard, current 77f29ff | 123 | 19 | 0 | 1 |

Nine formerly unsupported canonical references per suite now pass: tasks 78,
90, 91, 101, 112, 119, 120, 125 and 145. The remaining 19 unsupported IDs
in **each** suite are 3, 26, 27, 28, 29, 30, 34, 35, 76, 100, 109, 114, 115,
116, 123, 124, 135, 148 and 149. They include figures, DAGs, local runtime
jobs, noise/backend objects, packed-operation and wire limits, and external
array ownership. Task 82 remains a missing-file infrastructure outcome in
both suites. Exact details and per-task identities are in the comparison.

The extra observed hard pass is **task 63**, not a new interface improvement.
The earlier hard canonical run failed while this one passed with the same
completion hash. A separate [40-invocation protected repeat](GrayBench-v4-task63-canonical-repeat-77f29ff.jsonl)
(SHA256 `88f713a80bb266ec5d717388d2f64ef8ece7330ccb96973a76118e13a5b4c546`)
ran that canonical answer 20 times per suite: normal passed 1 and failed 19;
hard passed 0 and failed 20. The [repeat verification](GrayBench-v4-task63-canonical-repeat-summary-77f29ff.json)
(SHA256 `ac95dbe676d181c3ad89399d300d0a292128b055a7f71714151bc9bffceda7e7`)
checks the complete chain, source, probe hash, task identities, unchanged
completion within each suite and judge manifests. These 40 observations are
screening evidence, not an estimated provider failure rate. The prior
[exhaustive basis analysis](task63-oracle-review.md) explains the hidden RNG
coupling. Task 63 is release-ineligible in **both** suites until its public
randomness/output contract and oracle are revised; neither the hard pass nor
normal failure should be folded into a model ranking.

The [new full raw chain](GrayBench-v4-full-reference-77f29ff.jsonl) has SHA256
`3cdc77569b84d018f5fec6ac6226ea9c3d7438ed30ba5a7babdda1d9043bc425`
and chain head
`b013f0fe7980639d650c0e4117722752256c96bae1664f4e9a24fa826f755097`.
The old full scan and targeted task replays remain separate artifacts. Task
109's default-budget unsupported outcome is distinct from its successful
1,000-call diagnostics at much larger declared ceilings; those ceilings have
not been admitted uniformly. Task 116 still has the Rust-backed array
ownership limitation [documented separately](native-graph-hamiltonian-development.md).

This improves known reference-interface coverage, but many upstream tests
still accept incorrect solutions. Oracle/task-card review, resource calibration,
provider capability testing, reproducibility and independent review remain
mandatory before any fair model comparison.

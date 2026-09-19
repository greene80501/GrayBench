# Complete offline reference scan at f131336

The protected upstream scan completed all 286 planned cases, with 143 tasks in
each pinned suite. Eight external-service tasks per suite remained explicitly
excluded. The event chain verifies and contains no pending invocation.

| Suite | Pass | Unsupported | Infrastructure error | Total |
|---|---:|---:|---:|---:|
| Normal | 109 | 33 | 1 | 143 |
| Hard | 109 | 33 | 1 | 143 |

Compared with the complete 8399f3d baseline, tasks 37, 46, 86, 107, 141 and 149
now pass in both suites. No previously passing reference regressed in this single
replay. Task 82 still encounters the original upstream cross-process file
assumption; its explicit semantic recipe is not substituted into this scan.

The [machine-readable summary](GrayBench-v3-reference-summary-f131336.json)
preserves every outcome, transition, unresolved diagnostic, selection and source
identity. The complete local log is
`GrayBench-v3-reference-scan-f131336-worktree.jsonl`, SHA-256
`ae21613c70f9a65e96907181bcbcb32da7439014ca98902ad1e77810e378f480`.
The image was
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.

All executed engine bytes were guarded before and after every invocation. They
match f131336 after CRLF normalization; actual byte differences from Git blobs
are listed in the summary. Later documentation-only commits did not alter the
executed engine. This scan precedes the PropertySet transport change and does
not include its subsequent targeted results.

These are evaluator/reference compatibility counts, not model accuracy, oracle
correctness, flakiness bounds or task admission. Known false accepts and ambiguous
public contracts remain open. No model generation API was called.

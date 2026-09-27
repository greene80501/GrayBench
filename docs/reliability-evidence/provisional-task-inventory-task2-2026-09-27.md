# Provisional inventory after task-2 native-oracle review

The [updated machine-readable inventory](GrayBench-v4-provisional-task-inventory-task2-2026-09-27.json)
has SHA-256
`c1f2828892887cef113939f881a226729b3f40829aebe69822c90d7345ed3776`.
It was regenerated from both pinned 151-task parquet files with
`graybench.datasets.inventory`; its dataset digest remains
`85ebcebc15cf328869d67cba54ae2438394077aa74faa8a9b5835dc85488e6ba`.
The prior [20-family inventory](provisional-task-inventory-2026-09-27.md)
and its bytes remain preserved. This revision adds the
[native task-2 oracle finding](task2-statevector-oracle-review.md) to the normal
and hard task-2 cards, making 21 flagged families and 42 flagged variants.
The other 300 cards, dataset pins, release flags and pending review statuses
are unchanged.

All 302 cards remain `release_eligible: false`, with specification, oracle and
wire reviews pending. This is a review queue, not completed task admission or
a benchmark denominator. The task-2 probe was native and does not establish
how the protected bridge would handle the forged returns. Its release gate
requires a separate, predeclared oracle revision, positive and negative
protected controls, and independent review.

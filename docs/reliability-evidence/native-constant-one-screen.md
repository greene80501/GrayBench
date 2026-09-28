# Native constant-answer screen, 2026-09-27

The [source-bound chain](native-constant-one-screen-2026-09-27.jsonl) ran one
candidate that ignores all inputs and returns the Python string `"1"` against
every offline pinned task in both suites. In normal, the response was a newline
and an indented return statement appended literally to the public function
prefix. In hard, it defined the declared entry point with variadic arguments.
The normal cohort used `exact_prompt_suffix_v1`; hard used
`raw_or_single_python_fence_v1`. Both explicitly used
`test_exception_is_failure_v1` in the same Python 3.12/Qiskit Docker image as
the [canonical calibration](native-exception-policy.md).

| Suite | Planned offline tasks | `fail` | `pass` | Other outcomes |
| --- | ---: | ---: | ---: | ---: |
| Normal | 143 | 142 | 1: task 63 | 0 |
| Hard | 143 | 142 | 1: task 63 | 0 |

The chain is complete with no pending task. Every candidate reached the pinned
test phase; none was rejected by answer extraction or failed to launch. The two
passes reproduce the known task-63 fixed-string false pass. The public task
requires a sifted BB84 key from its basis and circuit, while the candidate
ignores both. The [independent basis enumeration](task63-oracle-review.md)
shows that `"1"` is not the answer for most valid receiver-basis choices for
the actual fixture. The [separate task-63 native control](native-reference-calibration.md)
also passed this constant candidate alongside the canonical answer.

This screen found no other survivor for this **one** fixed-string mutant. The
284 failures are not evidence that those tasks have adequate oracles: many
reject the wrong type or raise after receiving it, and other task-specific
wrong implementations are known to pass. The eight external-service tasks per
suite were excluded before freezing the 143-task cohorts. This is candidate
control evidence, not a model score, mutation-coverage percentage, or task
admission decision.

The chain's SHA-256 is
`bf9360e71153d9d7cab53b87d91b5dbe95c462f17103d157ac3a2f98f4c8f73c`;
its head is
`f57e0e6673daecec855882ddbdcf79243f941730f39cbf499e576de31ac6ff3f`.
The [probe source](native_constant_one_screen.py) has SHA-256
`2f3c5e61610a97c2eb3a4ca9b6d5417dc55c5b5e404366b254637742d3af5959`.
The bound engine source digest
`8d4d2ee6a6959e6f0c8bda91cea0120eaeb183e56fb31b34d7bc0b405c2358aa`
matched the local source at inspection; the image was
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
The evidence file preserves exact task, cohort, worker and judgment identities.

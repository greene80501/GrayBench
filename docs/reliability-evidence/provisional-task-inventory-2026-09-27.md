# Provisional paired task inventory, 2026-09-27

The [machine-readable inventory](GrayBench-v4-provisional-task-inventory-2026-09-27.json)
contains all 302 pinned normal/hard records: 151 task families in each suite.
It binds the public task and full judge-record digests, dataset pins, assertion
site counts, external-service flags and known review findings. Its dataset digest
is `85ebcebc15cf328869d67cba54ae2438394077aa74faa8a9b5835dc85488e6ba`.
Its byte-preserved JSON has SHA-256
`e208879eed4eaa48486adab812eacb318caec54efe70705a15603f77ce386ddc`.
Twenty families currently have specific known findings, so both variants of
those families are flagged. Every card retains pending specification, oracle and
wire review, empty independent-alternative and mutation-result lists, and
`release_eligible: false`. The inventory is a work queue, **not** 151 reviewed
task cards or an admitted scoring set. A family absent from `known_findings` has
not been shown sound.

The pinned normal and hard parquet files have respectively SHA-256
`1fb8d49195a08c023cc93b489b5d2ae0c2118047a5306f6fd374e3b4e95a94e6`
and `3809e1faa0d9bd3b2a366f2c25b36084705602d91318f30acffbd7e0b76df8c9`.
Each has 79 basic, 67 intermediate and 5 difficult records. Recompute from
`engine/` with `uv run --extra dataset graybench inventory ../data/datasets`;
the command prints JSON and makes no model API requests. The inventory does not
contain canonical code, private test bodies or model responses. The source of the
known findings and open review obligation is [the oracle audit](../ORACLE_REVIEW_FINDINGS.md)
and [the reliability plan](../RELIABILITY_PLAN.md).

An audited card must still state the input domain, output and side-effect
contract, semantic requirements, randomness, resources, external dependencies,
valid alternative implementations, deliberately wrong controls, evidence and
review decisions. An unexpected reference failure blocks admission for that
family; it must not silently change the eligibility denominator. The task-63
canonical repeat and the [published-score comparison](../COMPARISONS.md) show
why both dataset identity and oracle behavior must be frozen before any score.

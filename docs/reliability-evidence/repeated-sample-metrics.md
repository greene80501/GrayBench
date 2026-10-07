# Frozen repeated-sample metrics

`metrics-plan SETUP CACHE PLAN --k K` freezes requested opportunity metrics,
the full protocol, task/family records and analysis source before analysis.
Repeat `--k` for additional distinct values; pass@1 is always included and
its inclusion is visible in the saved plan. Every k must be at most the frozen
repeat count for every task. There are at most 100 distinct requested k values,
including one, and the existing protocol bounds repeats at 1,000. These are
explicit analysis bounds, not limits on an LLM's capabilities.

For n retained samples and c successes on one task, pass@k is computed exactly
as `1 - C(n-c,k)/C(n,k)`. This is the fraction of k-subsets of the retained
collection containing at least one success. It is the estimator used by the
[pinned OpenAI HumanEval implementation](https://github.com/openai/human-eval/blob/6d43fb980f9fee3c892a914eda09951f772ad10d/human_eval/evaluation.py).
Pass@1 is c/n. Overall scores average each task's fraction equally. The planned
balanced repeat counts make pass@1 agree with the ledger's single-answer mean.
The original `summary` schema and existing experiment identities are unchanged.

Pass@k describes opportunity with multiple candidates, and must not replace
single-answer reliability or be compared with another model's pass@1. It does
not measure how to identify a correct candidate without the correctness oracle.
This command neither selects an answer nor generates, repairs, retries or
rejudges anything. Interpreting the fraction as future independent k-draw
success requires iid sampling under a fixed generation policy. Correlated
generations and effective provider settings are not certified by the record.
Historical transport retries remain visible in the full protocol; these metrics
do not establish first-dispatch provider behavior.

`metrics PLAN LEDGER RUN CACHE REPORT` rebuilds exact task, request and family
bindings, verifies the protocol and ledger in one snapshot, and creates an
exclusive report. It opens only an existing ledger, in read-only mode. SQLite
may still manage WAL/shared-memory sidecars. Unsupported, infrastructure,
source-mismatched or missing samples keep the entire cohort unscored; no global,
per-task or family metric is produced. Candidate failures/errors/timeouts retain
the outcomes declared by the frozen judge and denominator policy.

Reports use `pass@1`, `pass@2`, etc. as metric names and retain exact rational
numerator/denominator strings with approximate floats. Per-task n, c and scores
are retained. Family breakdowns group the actual public-record family IDs;
they are descriptive and do not create independent observations. A family with
two task records keeps twice the global task weight of a family with one.
No implicit equal-family macro score or topic taxonomy is invented.
Native and protected runs retain their distinct, single-suite contracts;
historical mixed-suite cohorts remain labeled by their actual frozen protocols.

`metrics-verify PLAN LEDGER RUN CACHE REPORT` rebuilds the complete report and
compares canonical JSON. It rejects changed counts, mappings, k values, claims,
run bindings or source identity. Replay requires the same consistent ledger
snapshot: later appends can change global verification metadata. Archive
consistent SQLite backups after closure, rather than copying a live database
without its WAL state. Consistency is not external author authentication.

Plans should be frozen with the run selection/reporting policy before viewing
outcomes. These commands do not externally attest preregistration timing or
prevent an operator from selectively creating studies. All reports remain
development-only and `publication_eligible: false`. No confidence interval,
independent sampling certification, oracle admission, provider conformance or
runtime qualification is implied.

[Arithmetic and workflow evidence](artifacts/sample-metrics-2026-10-07/README.md)
compares a hash-checked, pinned HumanEval numerical function with exact fractions
and independently enumerated candidate subsets. Only that reviewed numerical
function executes; its module imports and candidate evaluator never run.
The reference file is supplied explicitly and rejected before execution if
any byte differs. Synthetic ledger/CLI tests cover retained denominators,
family weighting, complete/incomplete campaigns, separate tracks, tampering,
read-only file preservation and insufficient sample refusal. None is a model
benchmark score.

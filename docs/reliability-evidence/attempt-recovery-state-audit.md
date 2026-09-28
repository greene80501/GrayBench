# Attempt recovery contract of the development engine

This is a source-and-local-test audit at analysis-source digest
`05438b07b272b0d1ae8af293c8704e886d1ef2e6dd8538b88f162e335108aa0e`.
It documents behavior the replacement must preserve or explicitly revise.
No provider or model was called, and these tests do not certify a release.

On Windows with the engine virtual environment, the following focused tests
completed:

```text
pytest -q tests/test_campaign.py tests/test_ledger.py \
  tests/test_attempt_model_observation.py tests/test_model_observation_timing.py
45 passed
pytest -q tests/test_evaluation_campaign.py
5 passed, 1 skipped
```

The source and tests establish these distinct persisted states:

| Durable boundary | Current restart/next-step result | Evidence |
| --- | --- | --- |
| No attempt committed | The sample is ready for its first dispatch. | `Ledger.dispatch_state`; `test_source_drift_prevents_any_network_call` |
| Attempt intent committed, no delivery committed | The sample is `unresolved_delivery`; the runner does not replay. The ledger cannot tell whether the HTTP request went out. | `test_uncertain_delivery_stops_without_automatic_replay`; `test_unfinished_delivery_keeps_its_distinct_stop_reason` |
| Ambiguous delivery committed | The sample remains `unresolved_delivery`, including after a timeout. | Same tests; `Ledger.dispatch_state` |
| Explicit transient HTTP error committed | A retry of the same prepared request is permitted after frozen backoff and a fresh model observation. Restart preserves the backoff. | `test_restart_respects_persisted_backoff_and_never_replaces_answer`; `test_retry_binds_a_fresh_pair_of_observations` |
| Returned answer committed | The sample cannot generate another answer, including when the text is empty. | `test_empty_return_cannot_be_retried`; `test_empty_answer_and_permanent_rejection_are_never_retried` |
| Returned answer committed before its post-attempt model observation | The answer stays stored, but the run is `missing_post` and remains unscored. The post-observation token is returned to process memory by `finish_attempt` and cannot be recreated by an ordinary resumed call. | `test_missing_post_after_durable_return_cannot_be_silently_reobserved` |
| Post observation committed but protocol-3.3 timing check interrupted | The run is `missing_post_check` and remains unscored, even though the post observation row exists. | `test_crash_before_post_commit_check_keeps_run_unscored` |
| Judgment claim committed but judgment interrupted | The runner reports `unresolved_judgment` and does not silently rerun the oracle. | `test_interrupted_judgment_is_not_rerolled` |

These are conservative first-answer boundaries, but they are not a complete
recovery workflow. A pending delivery, missing post observation/check, or
unresolved judgment needs a terminal/adjudication path that preserves the
original attempt and evidence; an operator must not simply erase the claim or
resend the prompt. Any new release protocol should define the exact allowed
recovery evidence and which failures leave the run unscored. It must also
test process death at each durable boundary, reopening the same ledger before
deciding whether dispatch or judgment is allowed.

The retry identity check compares the prepared request digest, not an
observed exact wire request or non-secret credential/account scope. The
[request-scope probe](request-scope-provenance-audit.md) shows that changing
the credential under one environment-variable name leaves the digest
unchanged. The current tests' matching mock request bodies therefore cannot
prove matching account scope after a real process restart.

The current `rejected` classification is narrower than the desired proof of
non-acceptance: HTTP 429/500/502/503/504 status alone permits a retry, even
though the provider may have done model work. The separate
[503 ambiguity probe](http503-retry-ambiguity-audit.md) reproduces this risk
with a local mock. A release-safe retry needs provider-specific non-acceptance
or idempotent retrieval evidence; the passing recovery tests do not supply it.

The event chain, row bindings and append-only SQLite triggers protect against
accidental edits in this local engine. They do not provide an external chain
anchor or prove effective model settings. The replacement's publication gate
must check those separately.

Subsequent work added a narrow `recover-post-check` command for a committed
protocol-3.3 post observation missing only its timing check. It records the
actual recovery time and preserves a late violation; the other pending states
in this audit still need explicit adjudication.

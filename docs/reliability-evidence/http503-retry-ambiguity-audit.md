# An HTTP 503 does not prove a generation was rejected

This is a development-path audit at analysis-source digest
`05438b07b272b0d1ae8af293c8704e886d1ef2e6dd8538b88f162e335108aa0e`.
It uses local synthetic HTTP responses only. It neither shows that a real
provider lost an answer nor alters historical attempts.

`Transport.generate` currently classifies every HTTP status at least 400 as
`rejected`, before parsing the response as a model generation. The default
`RetryPolicy.statuses` includes 429, 500, 502, 503 and 504. `Ledger.begin_attempt`
permits another attempt after a `rejected` delivery with one of those statuses;
`GenerationRunner.step` can dispatch that next attempt after frozen backoff.
The existing `test_recovery_only_retries_explicit_transient_failure` confirms
the 503 path. A response status by itself does not establish whether the
provider accepted or completed model work before returning an error.

The [local mock probe](http503_retry_probe.py) returned a synthetic 503 body
with an `accepted` marker and first-answer text, followed by a synthetic 200
response to the same request bytes. The first delivery was `rejected` with
its raw response body retained as evidence but no `Generation`; the default
policy allowed 503 retry. The second delivery recorded a different returned
generation. The [saved result](GrayBench-http503-retry-probe.json) has SHA-256
`312edcdb90fe0fc4b99d1177364da5a47e1d504975d0794e2394dd4765619374`
and binds the probe source. No network service, account, or model was called.

This is a first-answer integrity risk, not proof that a real 503 contained a
usable answer. When acceptance is unknown, replay may select a later answer
and omit the first from the generation ledger. A release-grade retry policy
must require provider-specific evidence that the request was not accepted, or
a documented idempotency mechanism that retrieves the same generation. Other
uncertain failures must remain unresolved for adjudication. A bare transient
HTTP status must not be treated as that evidence. Historical development
attempts retain their original classification and cannot be silently
rescored as if this condition had been enforced.

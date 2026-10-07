# Protocol 3.2: attempt-bound model observations

The opt-in [protocol 3.3 timing revision](model-observation-timing-v33.md)
bounds how old an attempt's pre-observation may be and how long after delivery
the post-observation may be recorded.

Protocol 3.1 records a provider metadata observation before each generation request,
but cannot show which metadata was observed after a particular response. Protocol
3.2 is an opt-in development revision. It binds a pre-observation to an attempt
at durable dispatch and binds a fresh post-observation after the delivery and any
returned generation are durably saved. The pre binding names the exact observation
returned to the caller; a newer intervening observation aborts dispatch. The
delivery transaction stores the digest of a random, one-use post token and returns
the token to the live runner only. A restarted runner cannot recover it from the
ledger to attach a delayed check. These bindings and the token claim are append-only
relational rows covered by the ledger event chain. The observation includes the
credential-redacted provider metadata response, bounded HTTP evidence, a raw-wire
digest when available, and the derived identity status.

For a returned answer followed by metadata drift or outage, the answer remains in
the ledger. The drift or error also remains, further dispatch and judgment stop,
and the run summary cannot produce a completed score. A process interruption
between delivery and post-observation leaves `model_post_observation_missing`;
the next step does not silently use a later observation as if it were immediate.
An unfinished HTTP exchange instead remains `unresolved_delivery`. Rejected
attempts also receive post-observations, and a retry gets its own fresh pair.
Direct ledger dispatch requires the exact pre-observation ID; direct judgment cannot bypass
missing or unstable exposure evidence. A declared no-endpoint
`unverified_development` identity remains allowed only for a development score,
with its existing publication blocker.

The offline [test fixtures](../../engine/tests/test_attempt_model_observation.py)
exercise wire ordering, stable identity, drift, outage, interrupted delivery,
crash-like missing post, retry pairing, cross-run rejection, direct-call gates and
event-binding tampering using `httpx.MockTransport`. No model API generations are
made. Protocol 3.1 and its existing evidence are unchanged. The database still
requires trusted ownership and external anchoring of event-chain heads for
release provenance.

Pre/post equality is **not** proof that the provider ran identical weights or
settings throughout the generation request. Provider metadata is self-reported,
may omit mutable routing and compute parameters, and can change between these
checks. A trusted host operator could deliberately save or leak a live post token,
so timestamps and independent review still matter. Effective-setting probes,
snapshot pinning, task admission, protected
judge controls and independent reproduction remain separate release gates.

The complete local Python 3.12 offline suite on source-manifest digest
`78402854f349b26bcc08c2cb170bb83aa72bc1d75298f5b78b6aaedf76e2052d`
finished with 897 passed, 219 skipped, zero failures and zero errors. Its external
JUnit record has 1,116 tests and SHA-256
`b13936808e00d430d0f68117300f56d28686fa6abb114a4b117eb2ccc5731de7`.
The skipped cases include Docker-protected controls because Desktop is down;
this does not establish a protected judgment result. Ruff check and format
checks passed, and an independent read-only review found no remaining Critical
or Important issue. The reviewer noted that the live token does not bound
elapsed time before the post request.

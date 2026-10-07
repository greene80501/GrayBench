# Request bytes and credential scope are not yet attested

This is a read-only audit of the development transport at analysis-source
digest `05438b07b272b0d1ae8af293c8704e886d1ef2e6dd8538b88f162e335108aa0e`.
It does not alter a saved attempt or call a provider.

`PreparedRequest` freezes the adapter, model, API path, JSON body, and
setting evidence. `Transport._exchange` sends `canonical(body)` through
`httpx` and stores the structured `request_body`, base URL, path, and method
in delivery evidence. It does not persist the observed sent body bytes,
their independent digest, content-affecting request headers, or a non-secret
credential/account scope. Its `wire_sha256` field hashes the **response**
bytes, not the request. The current body can be reconstructed from the
recorded JSON and frozen transport code, but this is weaker than retaining
the observed transmitted request identity required by the proposed dual-track
headline reuse gate.

The [local mock probe](request_scope_probe.py) dispatched the same prepared
OpenAI-style request twice, using two deliberately fake token values under the
same environment-variable name. The mock endpoint observed different
Authorization headers but byte-identical JSON bodies. Both requests had the
same `PreparedRequest.digest` and `ModelSpec.digest`; neither delivery
evidence recorded a credential scope. The
[saved result](GrayBench-request-scope-probe.json) has SHA-256
`6f1f409d3774e45b827bcf1811eab16c6097946ac4be328700329cb07c4d934b`
and binds the probe source digest. It prints no token, secret-derived hash,
model answer, or host metadata. The mock used no network or billing account.

This does not show that a current recorded answer was sent to the wrong
account, nor that the provider altered the request body. It shows that a
credential rotation or account switch under one environment-variable name is
not distinguished by the frozen public request and model-spec identities.
The future release manifest should bind a non-secret provider account/project
scope and an attested content-bearing request identity before generation.
The sending adapter should retain the observed request body bytes or digest
and the relevant header names and non-secret values, with credentials excluded.
Cross-track headline reuse should require this identity and the matching
response, task contract, and extraction identity; historical attempts cannot
gain missing observations retroactively.

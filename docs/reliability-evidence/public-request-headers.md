# Public request-header provenance, 2026-09-27

Before this revision, the prepared-request digest bound the path and JSON body
but not the headers GrayBench passed to HTTPX. An adapter's authentication
method could override `Accept` or `Content-Type`, and an injected HTTPX client
could add defaults such as a model-mode header, cookie or query parameter.
The ledger would still show the original prepared request. This was a request
provenance gap, not evidence that a live provider changed a model answer.

New prepared requests include a canonical `public_headers` map in their
content identity. It freezes JSON content negotiation, identity response
encoding, a generic `python-httpx` user agent, and any adapter-declared
non-secret extension. Header names are lowercase and unique. Credential,
routing, framing, control-character and base-header overrides are rejected.
The prepared-request identity also freezes the exact credential header *name*
to send, or an empty set for a request without credentials. Only one supported
credential field may be omitted from public evidence. For `Authorization`,
the value must be exactly `Bearer ` plus the supplied secret; for supported
API-key fields, it must be exactly the secret. Presence, name and this public
format cannot vary at dispatch. Other authentication formats require an
explicit adapter contract revision before use. Credential values are never
written to request evidence. A directly known credential value is also
rejected if it appears in a public header before a prepared request is saved
or dispatched.

Before network I/O, the transport checks the current adapter declaration
against the frozen map, builds one HTTPX request, then checks its URL, method,
body, host, public and credential headers, and content length. Undeclared
client headers, cookies, query parameters and request or response hooks stop
the call before it is sent. That same checked request is sent with client
authentication and redirect following disabled. Evidence retains the frozen
map, its SHA-256 identity, the checked non-secret HTTPX header map and its
identity, the JSON body digest and length, and credential header *names*.
Generation first takes a deep snapshot of the prepared request; exchange also
copies headers and body before calling adapter authentication code. A plugin
retaining a mutable reference to the original request therefore cannot change
the sent bytes or make the recorded body describe different bytes during that
callback.
Fixture tests observed the previously hidden client defaults and verified
the new pre-send rejection. No live provider call was made for this revision.
The final pinned Python 3.12/Qiskit Docker-enabled engine suite completed with
1,317 passed, 5 skipped, and 6 expected failures in 654.43 seconds.

The checked HTTPX request is a client-side observation. It does not prove
remote receipt, TLS bytes, intermediary behavior, or the effective model and
settings. A credential can select an account or project with different server
behavior; the declared scope is not provider-attested. An installed adapter
can also change its code independently of GrayBench's source manifest;
plugin code attestation and provider conformance remain release gates.
Historical prepared requests omit the frozen header fields and retain their
original digest. They remain readable but cannot be dispatched under the new
transport.

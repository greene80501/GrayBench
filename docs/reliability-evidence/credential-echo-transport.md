# Credential echo in a successful provider response

The HTTP transport stores redacted response evidence so API credentials cannot
be copied into the attempt ledger. Previously, it also parsed that redacted
body as the model answer. A successful response whose text happened to contain
the configured credential could therefore be recorded as a **returned,
modified** answer and sent to the judge. A successful model-discovery payload
could likewise become changed metadata. This did not require a provider API
call to reproduce: a deterministic HTTP mock returned code containing its
configured test credential. Before the change, the generation test failed
because the transport classified that altered code as `returned`.

The transport now retains only redacted response text in durable evidence but
classifies a successful credential-echo response as `CredentialEcho`. Generation
delivery is `ambiguous`, with no normalized answer; discovery records an error
observation, with no altered metadata value. Existing ambiguous-delivery rules
stop automatic retries and further dispatch; the affected sample has no answer
to judge because the provider may already have generated and billed it. The
SHA-256 still identifies the raw received
bytes without saving the credential-bearing body. HTTP error responses retain
their existing redacted, rejected-delivery behavior.

The behavior is covered by the successful-generation and successful-discovery
mock regressions in `engine/tests/test_providers.py` and
`engine/tests/test_hosted_discovery.py`, alongside the existing HTTP-error
redaction test. This is a narrow transport-integrity fix. It does not attest
effective provider settings, weights, or the correctness of any model answer.

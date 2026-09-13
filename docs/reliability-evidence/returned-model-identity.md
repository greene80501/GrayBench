# Returned model identity policy

Protocol 3.1 adds an explicit returned-model policy to ModelSpec. By default the provider's
returned model name must exactly match the requested model. A frozen accepted_returned_models
list can instead declare known snapshot/alias names, with nonempty model_identity_evidence.
The mapping must be supplied before campaign creation; it is not learned from a surprising
answer and is not automatically expanded during resume.

Missing, empty or unexpected returned names do not discard the generation. The saved answer
and provider evidence remain intact, while further dispatch is blocked and aggregate accuracy
is unavailable, even if a separate judgment already recorded a pass. Reports include accepted
and observed names plus missing/mismatch counts. Matched names are labeled matched_declared_names
and weights_identity remains not_verified.

Tests cover missing/empty/unexpected identities, preservation of the original answer, dispatch
blocking, score suppression, a predeclared snapshot mapping and required mapping evidence.
The protocol schema is deliberately advanced from 3.0 to 3.1: older manifests are rejected
rather than silently assigned a new identity policy. Historical ledgers and artifacts remain
unchanged and can be read/replayed with their recorded original engine source.

This does not establish that weights remained unchanged behind a stable hosted name. Required
next evidence includes provider discovery, Ollama model digests and relevant server/model
configuration, hosted snapshot/alias documentation, and a declared policy for unavailable
identity information. Model metadata and oracle/task certification remain separate concerns.

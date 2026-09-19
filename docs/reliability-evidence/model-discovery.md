# Persistent model discovery evidence

campaign-observe appends provider discovery observations and a derived identity to the run ledger.
For Ollama, required records are server version, model catalog and show details. Exactly one
catalog entry must match the requested model name; aliases are not guessed. The identity binds
its SHA-256 model digest, server version and show configuration, excluding modified_at. Running
model/load-state observations are retained but do not create identity drift by themselves.

The API fields follow the [Ollama API specification](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml)
and [show-model documentation](https://docs.ollama.com/api-reference/show-model-details).
This remains server-reported metadata, not independent verification of model weights.

Once a run has an observation baseline, GenerationRunner refreshes discovery before each new
dispatch. Changed or unavailable identity leaves all evidence intact, stops generation and
suppresses aggregate accuracy. Later observations do not erase an earlier discrepancy. Tests
change the mock model digest after establishing a baseline and verify that no generation request
or attempt record is created. Invalid digests and irrelevant volatile changes are tested too.

Development runs without a baseline remain explicitly not_observed and uncertified. The current
implementation does not enforce pre-first-generation discovery admission; collecting a baseline later does not prove earlier model identity. Observation
and generation are separate requests, so a server could change between them. Required release work
includes snapshot pinning, pre/post observations and time-of-check policy, strict admission rules,
broader provider coverage and effective-setting conformance tests.


## Hosted metadata observations

OpenAI Chat/Responses and Gemini now retrieve the requested model's metadata with
one native GET request. The model component is URL-encoded; Gemini accepts the
public models/ prefix. Required identifiers must match exactly. Declared returned-
answer aliases are not used to guess metadata aliases. OpenAI records require the
model object, exact ID, creation timestamp and owner. Gemini records require the
exact name, version, positive input/output limits and generateContent support.
Missing or mismatched required fields leave the observation unresolved.

The derived fingerprint binds the full returned metadata object, adapter and base
URL. Unknown fields are retained, so changes to descriptions or other provider
metadata also require adjudication. This conservative policy can stop for a harmless
metadata change; it cannot establish immutable weights or equivalent compute.
Neither advertised defaults nor advertised limits are promoted to verified effective
settings. OpenAI's model resource does not supply Gemini-style token limits, and none
are invented. [OpenAI retrieve-model reference](https://developers.openai.com/api/reference/resources/models/methods/retrieve),
[Gemini model resource](https://ai.google.dev/api/models).

Every discovery observation now includes bounded transport evidence: method, base
URL, path, HTTP status, observation time, latency, allowlisted response headers and
the credential-redacted response body. Failed requests retain their evidence too;
non-finite or unrepresentable JSON becomes a recordable error. The wire SHA-256, when
available, describes bytes received before credential redaction; stored bodies are
explicitly redacted. Authentication headers and environment-variable values are not
stored. Duplicate observations cannot silently overwrite an identity input.

The existing optional-baseline policy applies unchanged: once observed, every dispatch
refreshes metadata and any discrepancy or unavailable observation remains unresolved.
An unchanged baseline allows dispatch. No baseline is still development-only; it is
not automatically accepted for a certified release. Older source-frozen runs should
continue to be inspected and executed using their original engine, not retroactively
relabelled with these new metadata semantics.

Validation: 313 tests passed with Docker enabled (zero failures/errors/skips),
including native endpoint requests, persisted raw/error evidence, credential redaction,
wrong model identities, duplicate observations, stable dispatch, drift/unavailability
blocking before an attempt, and malformed numeric/deep JSON. Ruff checks passed.
Six real read-only requests (two per adapter) against GPT-4o mini's dated model and
Gemini 2.5 Flash returned stable observations. The saved live SQLite ledger verified,
and contained zero generation attempts. These observations demonstrate metadata
integration, not generation billing readiness, live decoding conformance or model scores.

# Persistent model discovery evidence

campaign-observe appends provider discovery observations and a derived identity to the run ledger.
For Ollama, required records are server version, model catalog and show details. Exactly one
catalog entry must match the requested model name; aliases are not guessed. The identity binds
its SHA-256 model digest, server version and show configuration, excluding modified_at. Running
model/load-state observations are retained but do not create identity drift by themselves.

The API fields follow the [Ollama API specification](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml)
and [show-model documentation](https://docs.ollama.com/api-reference/show-model-details).
This remains server-reported metadata, not independent verification of model weights.

GenerationRunner now records a discovery baseline immediately before the first ready dispatch,
then refreshes discovery before every later dispatch. Changed or unavailable identity leaves all
evidence intact, stops generation and suppresses aggregate accuracy. Later observations do not
erase an earlier discrepancy. Mock endpoint tests verify the metadata-before-generation request
order for Ollama, OpenAI Chat/Responses and Gemini; unavailable first discovery creates no
generation attempt. Digest drift, invalid digests and irrelevant volatile changes are tested too.

An adapter with **no discovery endpoint** can run an explicitly unverified development campaign.
The frozen `ModelSpec` must set `discovery_policy: "unverified_development"` and a nonblank
`discovery_exception_reason`. Its synthetic unavailable observation and operator reason remain
in the append-only ledger; `discovery_status` reports `unverified_development`, and the summary
adds `model_discovery_unverified` to publication blockers. Without that declaration, the first
dispatch stops. A declared exception cannot bypass an adapter that advertises discovery:
metadata errors, mismatches and drift still stop before a generation attempt. This allows
development testing of APIs without metadata endpoints while preventing the resulting score
from being presented as an observed-model benchmark result.

The built-in [OpenAI-compatible Chat development route](openai-compatible-development.md)
uses this policy for services whose Chat Completions wire interface is usable but
whose model metadata route has not been established. Selecting that route does
not turn a failed strict OpenAI metadata request into verified discovery.

Lower-level ledger APIs can still create development attempts without discovery; such runs remain
explicitly not_observed and uncertified. The campaign runner's pre-dispatch observation does not
make metadata and generation atomic: a provider or local server could change between requests,
and the final generation has no post-dispatch observation yet. Required release work includes
snapshot pinning, pre/post observations with attempt binding and a time-of-check policy, strict
admission rules, broader provider coverage and effective-setting conformance tests.


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

Campaign dispatch now requires its first discovery observation as well as later refreshes.
An unchanged observed baseline allows dispatch; any discrepancy or unavailable observation
remains unresolved except for the frozen no-endpoint development exception above. Direct ledger
attempts without a baseline are still development-only.
Older source-frozen runs should continue to be inspected and executed using their original
engine, not retroactively relabelled with these new metadata semantics.

Previous metadata-transport validation: 313 tests passed with Docker enabled (zero failures/errors/skips),
including native endpoint requests, persisted raw/error evidence, credential redaction,
wrong model identities, duplicate observations, stable dispatch, drift/unavailability
blocking before an attempt, and malformed numeric/deep JSON. Ruff checks passed.
Six real read-only requests (two per adapter) against GPT-4o mini's dated model and
Gemini 2.5 Flash returned stable observations. The saved live SQLite ledger verified,
and contained zero generation attempts. These observations demonstrate metadata
integration, not generation billing readiness, live decoding conformance or model scores.

The first-dispatch preflight change has a red/green regression for missing initial metadata:
before the fix, the runner sent `/api/chat` without discovery and made an attempt after a
simulated metadata outage; after the fix, it records the outage and creates no attempt.
The complete pinned-image Docker suite then passed 1,028 tests with one skip and zero
failures/errors in 525.03 seconds. The JUnit record has 1,029 tests, zero failures/errors
and one skip. The skipped experimental Hamiltonian definition check is unavailable in the
original runtime. This validates the implementation path, not provider weight identity or
whole-cohort benchmark admission.

The explicit no-endpoint development policy was verified against a synthetic native adapter:
without the frozen exception, discovery stops before HTTP generation; with a reasoned exception,
the ledger records `unverified_development`, dispatches one answer and keeps
`model_discovery_unverified` in publication blockers. A failed Ollama metadata endpoint remains
unresolved even if a model spec declares that exception. The complete original-image Docker
suite passed 1,031 tests with one skip and zero failures/errors in 581.60 seconds; its JUnit
record contains 1,032 tests, zero failures/errors and one skip. These are implementation and
interface checks, not certification of the synthetic provider's model identity.

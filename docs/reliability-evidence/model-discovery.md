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
implementation does not enforce pre-first-generation discovery admission or provide hosted-provider
identity extraction; collecting a baseline later does not prove earlier model identity. Observation
and generation are separate requests, so a server could change between them. Required release work
includes snapshot pinning, pre/post observations and time-of-check policy, strict admission rules,
provider-specific metadata extraction and live conformance tests.

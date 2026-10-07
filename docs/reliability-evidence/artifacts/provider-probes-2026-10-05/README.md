# Current-source OpenAI and Google access probes

These are client-side observations made on the evening of 2026-10-05 in
America/Denver (2026-10-06 UTC) against GrayBench source revision
`a9cac8620d132060fad40499ab9f8819a859e16f`. Each discovery was a
read-only metadata request. Each capability probe made exactly one fixed,
non-benchmark generation request. The six public JSON records are fixed by
byte length and SHA-256 in [the manifest](manifest.json). The local API key
values are absent; model specifications retain only environment variable
names and declared scope labels.

| Exact model | Metadata discovery | Generation probe | Local probe digest |
| --- | --- | --- | --- |
| `gemini-3.8-flash` | Observed | HTTP 200, returned | `8a6c177d6b1e5f94536fa9ddf296182fc91b5827736aeb1ade4e44f715ec3031` |
| `gpt-4o-mini-2024-07-18` | Observed | HTTP 200, returned | `7314d66a604b6e3d151c59a1b9cd41ead4b71aa8f683c563045024cf04976a14` |

Both generation records use `client-built-httpx-v2` request capture. They
establish current access to these exact API routes and local consistency of
the saved request and response records. They do not establish effective
sampling controls, future availability, Qiskit HumanEval success, endpoint
receipt attestation, or a publishable model score. Neither spec requested
sampling overrides. [Google's model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
and [OpenAI's model page](https://developers.openai.com/api/docs/models/gpt-4o-mini)
describe the provider-side model names; the saved HTTP evidence records what
these accounts observed on this date.

From `engine/`, with the locked Python 3.12 environment, verify exact bytes,
request construction, discovery, and generation records:

```sh
uv run --locked --extra dataset --extra qiskit --group dev python ../docs/reliability-evidence/artifacts/provider-probes-2026-10-05/verify.py
```

The verifier reconstructs requests from current engine source. Checkout the
recorded revision to reproduce the adapter digest if the source changes.
This evidence is locally hashed and unsigned; it is not independent provider
attestation. It does not change the development-only release status.

# Live provider access probes, 2026-09-28

These are client-side observations from three exact model specs at GrayBench revision `ae60bd4824e268610ee172827404c11589754e6c`. Each discovery was read-only; each capability probe made one fixed, non-benchmark generation request. The [manifest](manifest.json) fixes the original nine JSON files by byte count and SHA-256. Credential values are absent; model specs name only environment variables and declared account scopes.

| Exact model | Metadata discovery | Generation probe | Local probe digest |
| --- | --- | --- | --- |
| `gemini-2.5-flash` | Observed | HTTP 404, rejected | `c97a6e85310d225b19d4c4512d31bde3782b5080339bd96290a75e57318bbc31` |
| `gemini-3.8-flash` | Observed | HTTP 200, returned | `4d4d536ed9cb0653cb95b8f1afd1447fe36e3e30f04035e38696dc4372f14e7f` |
| `gpt-4o-mini-2024-07-18` | Observed | HTTP 200, returned | `bd2cc076dd97ba0e7ae6535e39db3991080dc8dfb00da82579cdf40adef95695` |

The Gemini 2.5 Flash response says this model is no longer available to new users on this project and directs them to Gemini 3.8 Flash. Its metadata being visible did **not** mean the project could generate with it. Google's [model catalog](https://ai.google.dev/gemini-api/docs/models) and [Gemini 3.8 migration guide](https://ai.google.dev/gemini-api/docs/generate-content/latest-model), and OpenAI's [GPT-4o mini model page](https://developers.openai.com/api/docs/models/gpt-4o-mini), were checked on this date; the saved HTTP records establish only what these accounts observed then.

From `engine/`, with its locked Python 3.12 environment, verify the copied bytes and local record consistency:

```sh
uv run python ../docs/reliability-evidence/artifacts/provider-probes-2026-09-28/verify.py
```

This verification reconstructs the fixed request under the current engine source. The adapter digest covers the engine source, so a future source edit can make verification fail; check out the recorded revision to reproduce this check. The manifest and response hashes are local, unsigned evidence, not independent provider attestation. None of these probes requested sampling controls or measured their effective behavior, token limits, code quality, QHE task success, or benchmark score. Access can change. `publication_eligible` remains `false`.

# Local OpenAI-compatible route pilot (development only)

On 2026-09-27, the source at `af73e6b` made one real, sequential local
campaign through Ollama 0.34.4's `/v1/chat/completions` route. The frozen
`openai-compatible-chat` model specification named `qwen3:8b`, requested no
optional settings, and used the explicit `unverified_development` discovery
exception. There was no system prompt or answer repair. The two preselected
slots were task 0 in the pinned normal and hard suites, using the separate
`qhe0-size-domain-v1` semantic recipe. This was a transport and judgment
pilot, **not a representative model benchmark or publication-eligible score**.

The campaign completed with one returned response and one protected judgment
per slot, with no dispatch retry. Normal task 0 passed. Hard task 0 produced
`candidate_error` because the frozen `raw_or_single_python_fence_v1`
extractor saw multiple fenced blocks. Its response included a function block,
a separate example-call block, and a non-Python diagram block; the extractor
rejected the entire answer before executing code. The raw answer remains in
the external ledger, unchanged. This is concrete evidence that extraction
policy can affect a chat model's result even when it returns a candidate
function. It does **not** establish that selecting the function would pass
the task. Any less restrictive rule needs a new, predeclared protocol and
adversarial controls before evaluating models; this attempt must not be
rescored retrospectively.

The ledger verifier reported 12 bound events and chain head
`b5a9656e22c46b8e04913999b99399e72015de419bca733d8696ccb6386edd59`.
The complete two-slot summary reported `development_only`,
`publication_eligible: false`, and the blockers
`reviewed_task_and_protocol_admission_required`,
`independent_reproducibility_required`, and `model_discovery_unverified`.
The frozen and observed engine source digest matched:
`5e481aa68c63831308207f749eb597e5015813f39a5b91db1695b1ece78db8eb`.
Returned model names matched `qwen3:8b`; weights identity was not verified.
The ledger has no external chain anchor.

The external records are under `work/outputs/` and are intentionally not
included in Git because the SQLite ledger contains raw model responses and
protected judgment evidence:

| Record | SHA-256 |
| --- | --- |
| `GrayBench-v4-compatible-qwen3-8b-task0.sqlite` | `d3aaba03cf9b6f11c3cda6e288345641df2f5ee59427de06209d8de5f5c3d1fa` |
| `GrayBench-v4-compatible-qwen3-8b-task0-setup.json` | `261440d20fc6f0540c885a239238857c35d6e03d0d3694e5c652a472490db588` |
| `GrayBench-v4-compatible-ollama-qwen3-8b-model.json` | `a114e79a2ed616ec95de83f78d965406812cd577fffb269d99ee12a531ede541` |
| `GrayBench-v4-compatible-qwen3-8b-ollama-before.json` | `acab89a171ae18406a5f48633f9d817afa014a96cc588da98e5b28d3df2f5476` |
| `GrayBench-v4-compatible-qwen3-8b-ollama-after.json` | `021fe79f0e86eb303194cbb21f33e866f12e4fceef8b1e30b1a7b02a47df8542` |

The separate Ollama `/api/version` and `/api/show` observations before and
after the run both reported version 0.34.4, catalog digest
`500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`,
and identical model details and model-info fields. These observations are
outside the ledger and are not an attestation of the effective weights,
template, sampling defaults, or per-request server configuration. The adapter
and pilot remain development-only until that capability and identity profile
is independently established.

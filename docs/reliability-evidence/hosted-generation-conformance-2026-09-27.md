# Hosted generation conformance, 2026-09-27

This is a **development integration check**, not a model comparison or an
admitted benchmark score. It exercised the real provider adapters, frozen
campaign setup, model observations, append-only attempt ledger, and protected
Qiskit judgment on one task family in normal and hard. The task cards and
judge protocols remain release-ineligible.

The OpenAI and first Google setups were saved before generation. Each selected
`normal/qiskitHumanEval/0` and `hard/qiskitHumanEval/0`, one answer per task,
the separately named `qhe0-size-domain-v1` revision, protocol 3.3 pre/post
model checks, the default `raw_or_single_python_fence_v1` extraction, no system
prompt, and no requested sampling settings. The candidate and judge image was
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
(Python 3.12.14, Qiskit 2.4.2). Generation source digest was
`ea0f22f9f5b30d12fe8f6cb8fa5b23dc1fa174c230489604e8580c302390655d`.
The default provider behavior is not verified equivalent across models.

| Frozen run | Provider and declared model | Delivery and protected outcomes | Status |
| --- | --- | --- | --- |
| `5c4c4af464114a79af683ef55258799e` | OpenAI Chat, `gpt-4o-mini-2024-07-18` | Two returned; normal pass, hard candidate-format error | Development only |
| `85c948d4be03482fade29ff556c09a20` | Gemini, `gemini-2.5-flash` | First request rejected HTTP 404; zero answers returned or judged | Unscored |
| `ed150de3110b434a8ba7fef2886d93ac` | Gemini, `gemini-3.8-flash` | Two returned; normal and hard candidate-format errors | Development only |

The Gemini 2.5 response said this model was unavailable to new users on this
project. GrayBench retained that rejected attempt and did not substitute a
different model inside the run. A **new setup and ledger** selected 3.8 Flash.
Google's [2.5 Flash model page](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)
describes restricted new-user access, while its
[3.8 Flash guide](https://ai.google.dev/gemini-api/docs/generate-content/latest-model)
documents the current model and REST endpoint. The
[OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4o-mini)
lists the dated GPT-4o mini snapshot and Chat Completions endpoint. Those pages
document interfaces and availability; they do not prove the providers' actual
weights or effective sampling controls for these calls.

All three ledgers passed `graybench verify-ledger`. The two complete runs had
matching returned model names, stable provider-reported metadata, and complete
attempt-bound pre/post checks within their declared timing limits. Their
summaries remain `publication_eligible: false`; the HTTP rejection run is
`score_status: unscored`. No response was regenerated after an answer arrived.
The three exact local SQLite files, saved setups, and model specifications are
in `outputs/hosted-conformance-2026-09-27/` in the calling workspace. They are
not committed because the ledgers contain detailed host and response metadata.
Their SHA-256 values are:

| File | SHA-256 |
| --- | --- |
| `openai.sqlite` | `c8a33d026cb6d9b6dd41ccfb5967462e16d672a0006951620d242eb65452f949` |
| `gemini.sqlite` | `b728b36677e4f23421e4ecf6464dd9b694ea6255f360c7c72e0fa0ed3fe9c6ec` |
| `gemini-38.sqlite` | `ff6cd2110b57db7c6729ec9935111eb6192bc3c24f317969fa1f070210981337` |

A local scan found neither configured credential value in these saved files.
That check does not make the ledgers safe to publish indiscriminately. Their
hashes and SQLite append rules detect changes only against a separately
preserved baseline; they do not independently authenticate the machine owner.

## Formatting sensitivity, without rescoring

The original judgments used only frozen extraction v1. A later **read-only**
probe passed the four stored response texts through each extractor. It did not
execute selected code, alter a ledger, or create a revised score:

| Stored answer | v1 | v2 | New v3 |
| --- | --- | --- | --- |
| OpenAI normal | One Python block selected | Same block | Same block |
| OpenAI hard | Rejected: indented Bash fence | Rejected: indented Bash fence | Unique Python function selected |
| Gemini 3.8 normal | Rejected | Rejected | Rejected: three competing definitions |
| Gemini 3.8 hard | Rejected: two Python blocks | Unique function selected | Same function |

This illustrates why a single arbitrary formatting rule can alter measured
success. It does **not** show that the selected functions would pass the judge,
nor that v3 is universally fair. Any future v3 generation condition must be
frozen in its own protocol before requests; old v1 judgments stay as recorded.
The [v3 policy](extraction-protocol-v3-development.md) uses an explicit,
model-independent Markdown fence grammar and retains ambiguity checks.

The known [candidate serialization substitution](protected-worker-encoder-integrity.md)
and unfinished 302-card oracle review block score certification independently
of these provider and formatting observations.

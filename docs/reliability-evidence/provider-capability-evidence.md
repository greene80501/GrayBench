# Exact-model capability evidence, without effective-setting certification

GrayBench now accepts an optional `capability_profile` inside a model spec.
The record is frozen in the protocol and its digest is bound into each newly
prepared request. It names the exact adapter, model, base URL, and generation
path. Control entries cite an HTTPS document URL or a saved digest of a
non-benchmark request probe. A probe marked `probe_accepted` means only that
the endpoint accepted the request; it does not show that the provider honored
the control during generation. Historical specs and requests omit the new
field and retain their old identities.

For example, a development spec for `gpt-4o-mini-2024-07-18` may attach this
profile after checking the [official OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4o-mini)
on 2026-09-28:

```json
{
  "schema_version": "1",
  "adapter": "openai-chat",
  "model": "gpt-4o-mini-2024-07-18",
  "base_url": "https://api.openai.com/v1",
  "generation_path": "/chat/completions",
  "checked_on": "2026-09-28",
  "documentation": ["https://developers.openai.com/api/docs/models/gpt-4o-mini"],
  "probe_digests": [],
  "controls": {},
  "output_token_limit": 16384,
  "limit_evidence_refs": ["https://developers.openai.com/api/docs/models/gpt-4o-mini"]
}
```

The cited page calls 128,000 tokens a context window, not an input-only limit;
the profile leaves `input_token_limit` unset. The empty `controls` object makes
no claim about sampling controls or default
decoding. If a setting is requested, the exact model profile must cite
documentation or a contract-probe artifact for that control. The adapter
still checks that it knows how to serialize the field. GrayBench rejects a
setting marked unknown, ignored, unsupported, or absent from the profile.
An existing `Setting.support: verified` requires a saved accepted-request
probe; the word describes request support only, not effective decoding.

This distinction matters across provider versions. Google's
[Gemini 3.8 Flash migration guide](https://ai.google.dev/gemini-api/docs/generate-content/latest-model)
instructs clients to remove temperature, top-p, and top-k overrides for that
exact model. A generic `generationConfig` schema is not enough to infer that
those controls are effective for it. GrayBench keeps model-specific judgments
in the supplied profile rather than a universal Gemini adapter allowlist.

`summary` emits the frozen profile and digest with status
`operator_evidence_recorded`, or `missing` when no profile was supplied. It
also reports requested settings separately and labels effective settings
`not_attested`. Both cases remain publication-ineligible. This increment
does not validate document authorship or version, inspect a referenced probe
artifact, attest provider weights, or prove settings took effect. Provider
qualification, live contract probes, external evidence anchoring, and an
independent release decision remain necessary.

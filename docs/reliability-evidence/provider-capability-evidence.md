# Exact-model capability evidence, without effective-setting certification

GrayBench now accepts an optional `capability_profile` inside a model spec.
The record is frozen in the protocol and its digest is bound into each newly
prepared request. It names the exact adapter, model, base URL, and generation
path. Control entries cite an HTTPS document URL or a saved digest of a
non-benchmark request probe. A probe marked `probe_accepted` means only that
the endpoint accepted the request; it does not show that the provider honored
the control during generation. Historical specs and requests omit the new
field and retain their old identities.

A one-answer probe cannot establish an input or output token limit. New
campaigns reject a probe digest cited as token-limit evidence; cite
model-specific documentation for those claims.

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
does not validate document authorship or version, attest provider weights,
or prove settings took effect. External evidence anchoring, behavioral
qualification, and an independent release decision remain necessary.

## Capturing and freezing an accepted-request probe

Use a separate model-spec JSON with the exact adapter, model, base URL,
credential scope, and one or more settings to test. The settings use their
ordinary adapter-supported fields; a profile is not required for the probe.
This command makes **one billable generation call** with a fixed public prompt
that contains no QHE task and never judges the answer:

```sh
graybench capability-probe probe-model.json probe-record.json
```

The output path is reserved before dispatch and never overwritten. A
rejected or ambiguous delivery remains in the artifact for diagnosis; it
cannot support `probe_accepted`. A returned record must also pass the local
verifier, including the returned-model check. Only when
`qualifies_for_probe_accepted` is true should you copy its printed
`probe_digest` into the campaign model's `capability_profile.probe_digests`
and the relevant control's `evidence_refs`. Use the same requested value in
the campaign model spec. Then supply the record to `campaign-plan`,
`native-plan`, or `protected-plan` with `--capability-probe probe-record.json`.
Repeat that flag for each cited digest. Each setup embeds the full records, so
later verification does not depend on the original path.

Current `probe_accepted` qualification also requires
`client-built-httpx-v2` request evidence to be fully bound to the frozen
probe request. Body-only `canonical-body-v1` records remain readable for
historical inspection but cannot support a new accepted-control claim. The
probe verifier checks the capture version and identity accept-encoding as
well as its earlier request fields; changing either no longer leaves an
otherwise accepted probe qualified.

GrayBench reconstructs the fixed request with the current adapter and checks
its frozen body, headers, path, account-scope declaration, response hash,
parsed generation, returned model name when present, and requested control
values. Campaign planning, run creation, and resume reject missing or altered
records before benchmark dispatch. Reports distinguish
`verified_local_records` from `missing_or_invalid` and retain the separate
`provider_effective_settings_not_attested` publication blocker. A locally
consistent record can still be fabricated by someone controlling its file;
it does not independently prove remote receipt, active weights, or that a
sampling parameter had a behavioral effect. No live probes were run as part
of this implementation's tests.

# Provider capability evidence in frozen experiments

Status: implemented contract and reporting increment in the draft overhaul.
This does not qualify a provider, attest proprietary weights, or enable
publication.

## Purpose

A frozen HTTP body proves what GrayBench asked an endpoint to do. It does not
prove that an exact model supports a control or that the provider honored it.
GrayBench needs a versioned, model-and-endpoint-specific capability record that
travels with every new experiment and remains separately identifiable from
the request and provider response. Historical contracts must keep their exact
digests and remain readable.

The current `Setting.support` value is an operator assertion that the adapter
may serialize a setting. It is not a provider capability audit. Generic adapter
setting allowlists are endpoint mappings, not model support matrices.

## Evidence and record

An optional `CapabilityProfile` is stored inside `ModelSpec`, which is already
part of every frozen protocol and campaign setup. It names the exact adapter,
model, base URL, and generation path. It records optional input/output token
limits, HTTPS documentation URLs checked by the operator, content digests of
non-benchmark contract probes, and one evidence-backed request-support status
per named control: `documented`, `probe_accepted`, `ignored`, `unsupported`, or
`unknown`. Each non-unknown control cites the exact document URL or probe
digest in the profile. Token limits cite evidence in the same way. A probe
accepted by an endpoint establishes request acceptance only. Neither a
documentation statement nor a successful probe attests effective decoding.

The profile is content-addressed by the existing canonical JSON identity.
`ModelSpec` validates exact adapter/model/base-URL binding and refuses a
requested setting classified as ignored, unsupported, unknown, or absent.
An existing `Setting.support: verified` requires `probe_accepted` in the new
profile; that legacy word still does **not** mean effective behavior was
verified. A documented setting may cite documented or probe-accepted support.
The adapter validates the frozen generation path and binds the profile digest
into each new `PreparedRequest`. Historical requests and model specs omit the
new optional fields, preserving their hashes.

## Reporting and release boundary

The ledger summary reports the profile digest, exact model/endpoint, controls,
limits, and whether the record is absent. It labels the profile
`operator_evidence_recorded`, never `provider_verified`, and marks effective
settings `not_attested` unless separately reported by the provider. A profile
does not remove publication blockers. Comparisons continue to expose each
side's distinct profile and do not infer equivalent opportunity from matching
setting names or nominal values.

The first implementation does not fetch live documentation, issue billable
model calls, or create hard-coded provider matrices. Provider-specific profiles
and behavioral probes are later qualification artifacts. The current official
[GPT-4o mini model page](https://developers.openai.com/api/docs/models/gpt-4o-mini)
documents an endpoint and limits, while Google's
[Gemini 3.8 Flash migration guide](https://ai.google.dev/gemini-api/docs/generate-content/latest-model)
advises removing sampling overrides despite generic generation fields. These
pages were consulted on 2026-09-28 and illustrate why profile claims must be
exact to a model and date and why unknown effective behavior stays unknown.

## Verification

Tests must show exact identity/path matching, evidence-reference validation,
model-specific rejection of unsupported requested controls, unchanged
historical hashes, a changed prepared-request hash when capability evidence
changes, and truthful unqualified reporting. No test may treat an HTTP 200 or
provider metadata as proof of effective sampling or model weights.

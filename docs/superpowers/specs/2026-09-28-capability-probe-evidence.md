# Verifiable local evidence for provider capability probes

Status: design for the draft GrayBench overhaul. This is a request-acceptance
qualification step, not proof that a provider honored a setting or served a
particular proprietary weight revision.

## Purpose and boundary

The current exact-model `CapabilityProfile` can cite an arbitrary 64-hex probe
digest. A campaign can therefore freeze an evidence reference without the
referenced record. New campaigns must carry the actual non-benchmark probe
records and verify their content and endpoint before they claim
`probe_accepted` support. Historical artifacts remain readable; no legacy
digest or score is silently relabeled.

The user wants a fair benchmark of any local or hosted LLM. This increment
addresses accidental or unsupported provider-setting claims. It does not
turn a successful HTTP response into evidence of effective decoding, model
weights, equal token opportunity, or a publishable score.

## Chosen record flow

A `CapabilityProbe` records one call to a fixed, public GrayBench probe prompt,
made with a model spec that has no capability profile. The record contains the
unprofiled spec, full frozen `PreparedRequest`, one `Delivery` classification,
HTTP status, transport evidence, parsed generation when returned, and UTC
observation time. Its canonical digest is the reference used in a later
profile. A failed, rejected, or ambiguous call is still saved but cannot
support `probe_accepted`.

The request is unprofiled to avoid a circular identity: the later profile
references the probe digest, while a profiled request would itself contain the
profile digest. The `capability-probe` CLI makes at most one generation call
and writes an exclusive JSON artifact. It never sends a QHE task or judges a
response. Credentials remain in environment variables and are not serialized.

All three legacy, native, and protected campaign setups embed the exact
accepted probe records in an optional field. Their builders require the
embedded digest set to equal the profile's
`probe_digests`. For each record, an offline verifier reconstructs the fixed
probe request with the current adapter, checks model/endpoint/path, request
identity, request and response evidence hashes, status, parsed generation,
and the named controls used by that probe. A requested control supported by
`probe_accepted` must have been sent at the same value. Execution-context
and durable ledger creation repeat the verification. The report distinguishes verified local
probe artifacts from missing or invalid ones without claiming provider-side
effectiveness.

An external file path alone is not sufficient because it can disappear after
the campaign is created. Embedding the record in the profile would make its
digest circular with the request. Embedding it in the setup keeps an archived
run self-contained and leaves the model spec's existing identity unchanged.

## Error and compatibility rules

- An absent profile accepts no probe bundle and keeps historical identities.
- A profile with no probe digests accepts an empty bundle.
- A profile with probe digests cannot create a new setup or run unless every
  distinct digest has one accepted, internally consistent record; extra records
  fail. An archived run with no or invalid records remains readable but shows
  a publication blocker.
- Non-2xx, parse errors, credential echo, truncated delivery, malformed
  timestamps, mismatched request bodies, and changed adapter code fail
  qualification. They remain preserved as raw diagnostic records.
- The provider response and adapter's parsed generation are recorded as data.
  A local record can still be forged by its operator; external authenticity
  and independent review remain separate publication gates.
- Old setups and protocols omit the new optional field and remain readable.

## Verification

Use HTTPX fixtures with zero live provider calls. Red tests should show that a
bare digest, wrong endpoint, changed control value, changed response hash,
non-returned delivery, and extra or duplicate records cannot be frozen as
accepted probe evidence. A valid record must survive all setup JSON round-trips
and retain the profile's request digest. The complete pinned Docker-enabled
engine suite and changed-file lint run before updating the draft PR.

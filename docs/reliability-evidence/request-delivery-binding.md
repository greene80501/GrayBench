# Versioned request-to-delivery evidence binding

Before this change, the transport recorded the prepared request body, canonical
byte length and SHA-256, path, base URL, adapter identity, public headers and
credential scope in a delivery. The ledger bound that delivery to an attempt,
but did not compare those fields with the attempt's frozen `PreparedRequest`.
A mistaken or locally tampered pairing could therefore remain internally
hash-chain consistent.

The initial version marked `request_capture_version: canonical-body-v1`.
When that marker is present, `Ledger.finish_attempt` checks all of the fields
above, including the hash and length of the exact canonical JSON body, before
committing a delivery. Ledger verification repeats the check against the
saved attempt and delivery, so a consistently rehashed mismatch fails.
The summary reports counts of `bound` and `unbound` deliveries; any unbound
delivery adds `request_evidence_unbound` to publication blockers. Historical
evidence without the marker stays readable and is **unbound**, even if some
similar fields happen to be present. This preserves its earlier meaning
without retroactively claiming a stronger request link.

The subsequent `client-built-httpx-v2` capture tightens the meaning of
**bound**. It also requires the non-secret HTTPX headers constructed before
dispatch (including host and content length), their digest, the frozen public
header digest, and the declared identity accept-encoding. These fields must
agree with the frozen request and endpoint, even if a local record is edited
and rehashed consistently. Earlier `canonical-body-v1` deliveries still
validate their body-level claims, but are now reported as **unbound** because
they lack the complete client-built request snapshot. The version does not
claim that the provider received those bytes.

Host tests first reproduced accepted mismatches, then covered altered body,
hash, byte length, path, base URL and adapter digest; incomplete marked
evidence; a real mock HTTP transport-to-ledger path; and a rehashed tamper of
the saved delivery row and event. The complete pinned-cache host suite passed
with 1,294 tests and 272 skips. Docker-dependent controls remain unrun.

This checks GrayBench's local request construction and saved evidence. It
does not attest provider receipt, account identity, effective settings, or
the model weights that served a response. External anchoring and live
provider calibration remain required for a publishable comparison.

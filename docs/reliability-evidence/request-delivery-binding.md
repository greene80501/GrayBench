# Versioned request-to-delivery evidence binding

Before this change, the transport recorded the prepared request body, canonical
byte length and SHA-256, path, base URL, adapter identity, public headers and
credential scope in a delivery. The ledger bound that delivery to an attempt,
but did not compare those fields with the attempt's frozen `PreparedRequest`.
A mistaken or locally tampered pairing could therefore remain internally
hash-chain consistent.

New transport records mark `request_capture_version: canonical-body-v1`.
When that marker is present, `Ledger.finish_attempt` checks all of the fields
above, including the hash and length of the exact canonical JSON body, before
committing a delivery. Ledger verification repeats the check against the
saved attempt and delivery, so a consistently rehashed mismatch fails.
The summary reports counts of `bound` and `unbound` deliveries; any unbound
delivery adds `request_evidence_unbound` to publication blockers. Historical
evidence without the marker stays readable and is **unbound**, even if some
similar fields happen to be present. This preserves its earlier meaning
without retroactively claiming a stronger request link.

Host tests first reproduced accepted mismatches, then covered altered body,
hash, byte length, path, base URL and adapter digest; incomplete marked
evidence; a real mock HTTP transport-to-ledger path; and a rehashed tamper of
the saved delivery row and event. The complete pinned-cache host suite passed
with 1,294 tests and 272 skips. Docker-dependent controls remain unrun.

This checks GrayBench's local request construction and saved evidence. It
does not attest provider receipt, account identity, effective settings, or
the model weights that served a response. External anchoring and live
provider calibration remain required for a publishable comparison.

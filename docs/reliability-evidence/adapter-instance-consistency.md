# Adapter instance consistency, 2026-09-27

Before this revision, `Transport.generate` parsed a response with the supplied
adapter instance, but `_exchange` constructed another adapter from its name to
build authentication headers. Discovery similarly took requests from one
instance and credentials from another. This could change provider behavior for
a stateful installed adapter without changing the prepared request.

The transport now uses the supplied instance for request authentication and
response parsing during generation, and for both request discovery and
authentication during discovery. Discovery rejects an adapter whose name
differs from the frozen model before making a network request. The generation
path already had that identity check. Regression fixtures demonstrated the
old reconstruction and missing discovery guard before the change, then passed
afterward. They use a local HTTPX transport and a fixture credential; no live
provider request was made.

This is a per-call consistency rule. Campaign planning and later dispatch can
run in different processes and reconstruct an adapter from its registered
name. Frozen prepared-request digests detect changes to the public request,
but the current source manifest covers GrayBench package files, not installed
third-party plugin code. Plugin identity, content-affecting headers, and live
provider setting conformance still need release-level attestation. This check
alone does not qualify a plugin or certify a benchmark score.

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
The later [adapter code provenance change](adapter-code-provenance.md) adds a
bounded local source manifest for installed third-party plugins. That manifest
detects covered file drift; it does not attest plugin honesty, external
dependencies, provider behavior, or effective settings. Independent plugin
qualification and live provider conformance remain release gates. Neither
check alone certifies a benchmark score.

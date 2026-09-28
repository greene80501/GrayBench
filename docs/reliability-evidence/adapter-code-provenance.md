# Adapter code provenance, 2026-09-28

The engine source manifest already bound GrayBench's own Python files. A
third-party adapter loaded from `graybench.adapters` could change independently
while retaining the same registered name, request body and public headers.
The engine source digest and prepared-request digest alone did not identify
that plugin code. This was a provenance gap, not evidence that any provider
changed a benchmark answer.

New prepared requests bind a SHA-256 digest of a versioned adapter-code
manifest. New campaign protocols store that non-secret manifest. Exact built-in
adapter classes use the existing full engine source digest. A registered
external class entry point records its name, target and distribution
name/version, then hashes regular files in its one top-level package root.
An unregistered or directly supplied subclass is marked
`module_only_development` and hashes only its defining module. Registered
single-file modules receive a distinct limited-coverage label. File keys are
logical relative names; absolute host paths and file contents are excluded.
The package scan rejects missing or unreadable files and directories,
symlinks, Windows junctions, ambiguous namespace roots, entry-point targets
outside the class's top-level package, more than 4,096 files, more than 8,192
traversed entries, and more than 64 MiB of input. It
excludes transient caches (`__pycache__`, `.pyc`, `.git`, `.pytest_cache`,
`.ruff_cache`).

Campaign planning checks that every rendered request has the same adapter
digest as its protocol. Creation and resume compare the current adapter
manifest with the stored one. Model observation supplies the expected digest
to discovery, which checks before I/O and records the observed digest.
Generation checks the prepared request's adapter digest before I/O and again
after authentication callbacks while the HTTPX request is still unsent. A
mismatch stops the attempt; it never triggers an automatic replacement answer.
Historical requests and protocols omit these optional fields and keep their
original identities. They remain readable without being relabeled as having
this newer evidence.

Fixture tests use an installed-entry-point stand-in and edit its package data
between preparation and dispatch. Generation and discovery both reject drift
before MockTransport sees a request. A second fixture edits the package during
authentication and is also rejected before send. No live provider call was
made for this revision.

These hashes detect edits to covered local files. They do not attest an
adapter's honesty, imported dependencies or dynamically loaded code outside
the scanned package, mutable in-memory state, provider receipt, effective
settings, or model weights. A file can also change in the small interval
between the final local digest check and the network send. Independent plugin and provider qualification and
clean-machine reproduction remain release gates. Both Actions workflows are
manually disabled while GitHub billing is exhausted; local verification is
reported separately from CI.

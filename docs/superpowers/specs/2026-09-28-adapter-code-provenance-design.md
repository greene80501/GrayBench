# Adapter code provenance for development campaigns

## Intent and boundary

GrayBench already binds its own Python source to a campaign, but a named
`graybench.adapters` entry point can load third-party code outside that source
tree. The same adapter name and prepared body can therefore refer to different
code at planning and dispatch. Detect that drift before model discovery or
generation. Record enough non-secret information to reproduce the observation,
without calling a local hash a signature, independent review, or proof of a
provider's effective behavior.

The user authorized the broader auditable-benchmark rebuild and draft PR.
This increment is a development provenance gate within that approved scope;
it does not qualify arbitrary plugins or publish a model score.

## Approaches considered

1. Hash only the adapter class's module. This is cheap but misses helpers and
   package data, so a routine refactor can silently change behavior.
2. Hash the installed distribution's RECORD. This identifies an installed
   wheel but misses editable source changes and files loaded outside RECORD.
3. **Use a bounded package-tree manifest for registered plugins**, with the
   entry-point and distribution metadata, and a module-only manifest for
   directly supplied development adapters. Recompute at each boundary. This
   detects ordinary edits to a plugin's installed package without claiming
   the plugin is trustworthy. This is the selected approach.

## Manifest and identities

`adapter_code_manifest(instance)` returns a canonical, secret-free object with
schema `adapter-code-v1`, the adapter name, class module and qualified name,
coverage mode, and SHA-256 hashes of code/package files. Exact built-in classes
use GrayBench's existing full `source_manifest` digest. A registered external
adapter records its one entry-point name/value and distribution name/version,
then hashes regular files under the top-level imported package. A directly
supplied subclass or unregistered adapter records its defining module file and
is explicitly marked `module_only_development`. The manifest contains logical
module-relative paths, never absolute host paths or file contents. Reject
missing/unreadable source, ambiguous namespace-package roots, symlinks in the
scanned package, more than 4,096 files, or more than 64 MiB of scanned bytes
rather than silently downgrading coverage. Exclude `__pycache__`, `.git`,
`.pytest_cache`, `.ruff_cache`, and compiled `.pyc` cache files. Runtime-loaded
code outside that package and external dependencies are not covered; the host
environment's package inventory remains a separate observation.

New `PreparedRequest` objects carry `adapter_code_digest`, computed from this
manifest and included in their existing request digest. New campaign builders
store the full manifest in an optional `Protocol.adapter_code_manifest` field.
The field is omitted on historical protocols and requests, preserving their
serialized identities. The protocol validator requires a canonical manifest
when the field is present; builders and runners check its digest against
newly rendered requests. Historical campaigns remain readable and retain their prior
development semantics; they are not relabeled as having this evidence.

## Checks and data flow

Planning resolves the adapter, computes one manifest, renders all requests,
and checks every request's adapter digest against it. Creation/resume verifies
that the current adapter manifest matches the protocol before any discovery.
The discovery path repeats that check immediately before network access and
records the observed manifest digest. Generation checks the prepared-request
adapter digest against the supplied adapter instance before network access;
the existing source and request-digest checks remain in place. Mismatch is a
pre-dispatch error, never an automatic retry or a changed historical score.

The manifest is a *change detector*. A malicious plugin can invoke dynamic
code, misdeclare behavior, or use a provider that ignores settings. Independent
plugin review, provider conformance, account/model identity, clean-machine
reproduction, and external authenticity still gate release.

## Verification

Tests must demonstrate: built-in identity is bound; two source versions under
one plugin name produce different manifests; an edited plugin file stops a
planned request and discovery before MockTransport sees network I/O; an
unregistered development subclass cannot claim package-tree coverage;
historical artifacts round-trip unchanged; and no absolute path or credential
enters the manifest. Run focused tests, changed-file Ruff and formatting,
the complete pinned Python 3.12/Qiskit Docker suite, and an independent review.
Keep both GitHub Actions workflows disabled while billing is exhausted.

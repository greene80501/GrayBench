# Fixed public anchor registry implementation

PublicAnchorRegistry now captures the fixed public SDK singleton closure with
strong object references, frozen identity-to-key mappings and immutable serialized
bootstrap records. It is explicit and opt-in: callers must capture before user
code and retain that registry for the session. It is not yet attached to GraphArena
messages, private rehearsal or live commit, and therefore does not admit singleton
transport by itself.

key_for uses object identity, never value equality. resolve accepts only an existing
canonical string key with its captured graph kind and unchanged exact runtime
type. The registry manifest has a fixed version, bootstrap digest and node count;
mismatches and extra fields are rejected. Snapshot/record access returns fresh JSON
objects so a caller cannot rewrite stored bootstrap evidence. Live SDK value changes
do not alter those records or the manifest. Original detached children stay strongly
referenced; equal replacements receive no old anchor identity.

Capture limits nodes, edges and encoded graph bytes. Only the fixed public factory
table supplies roots. No private judge state, candidate code, arbitrary class path,
payload-selected constructor or lazy definition synthesis is used. The complete
bootstrap snapshot is for private preparation only and must not be attached to
ordinary call payloads. Future integration must send anchor labels only for objects
actually exported by a call.

## Verification

The initial test collection failed because graph_anchors did not exist. Nineteen
final focused cases pass: real factory/child resolution, equal replacement,
immutable returned records, stable bootstrap history after live value mutation,
manifest mismatches, noncanonical/unknown keys, kind mismatches and resource limits.

The runtime registry was compared with the earlier independent capture in fresh
Windows and Linux processes. Every one of the 676 identities resolves to the
same actual local object and kind in each process; complete bootstrap records
also match. Both produce the existing 30-factory, 74,434-byte graph hash:
e2923337f9e89609c3e2ad1f4d37e0bd4e17a585448831cef4e11980afefc1ce.

[Windows result](GrayBench-public-anchor-registry-windows.json), raw SHA-256:
ebe33363cd4290eb39bd6db29a2daf72441f6b609c2f293bdfc34a771ee788e2.

[Linux result](GrayBench-public-anchor-registry-linux.json), raw SHA-256:
d676a66d7eb9770450cbca973d6a2400b7c07289cad70b2aa3b7fe525eacfaa0.

Twenty dependency hashes and the fixture hash were verified against actual source
bytes. Linux used the pinned image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd,
readonly mounts, no network, uid 65534, 512 MiB memory, one CPU, 64 PIDs and a 16 MiB
tmpfs. This is trusted component validation, not protected benchmark admission.

The full Docker-enabled suite passed **767 tests** in 195.62 seconds, with no
failures, errors or skips. JUnit: outputs/GrayBench-v4-public-anchor-registry-full-tests.xml.
Ruff lint, 120-file formatting and secret-value diff checks passed.

Still required: strict graph anchor annotations, singleton node reconstruction,
private cloned anchor storage, actual live factory binding and initial native-owner
transition state, plus separate-process atomicity and identity regressions. The
production bridge remains v3; the original verdict defects and broader release
requirements remain open. No model generations or new cohort score were produced.

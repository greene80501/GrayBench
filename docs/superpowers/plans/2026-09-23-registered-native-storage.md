# Registered native storage implementation refinement

Status: native helper prototype under development; graph integration is not
implemented and the runtime is not admitted. The original benchmark objective
and release gates remain unchanged.

Current experiment: the two-phase registry, bounded read/write helper and native
array factory passed standalone native checks on a rebuilt SciPy image. An
AddressSanitizer harness first reproduced, then verified a fix for destructor
reentry during registry sweeping. Toolchain locking, capsule/root/view graph
nodes, protected execution, full suite and reference replay are still open.
These intermediate results are not benchmark scores.

## Evidence and decision

HamiltonianGate's cached definition introduces SciPy expm arrays backed by
PyCapsule. Native tests show different readonly behavior from owning ndarray
copies, and retained views remain writable. The fixed class-registry addition
alone leaves exact task116 unsupported and three new regressions failing.

The pinned SciPy source allocates a buffer, constructs the returned ndarray with
PyArray_SimpleNewFromData, and attaches a NULL-named capsule. Its destructor frees
the capsule pointer; no capacity is stored there. Python exposes capsule metadata
and setters, not a storage-extent query. Destructor comparison is not provenance.

Sources:
- https://github.com/scipy/scipy/blob/v1.18.1/scipy/linalg/_matfuncsmodule.c
  (downloaded source SHA256 e2e6897101a0743a8921c5aac18f767b626516e58f7f5d56bc0f54180dffd54d).
- https://docs.python.org/3.12/c-api/capsule.html
- docs/reliability-evidence/native-capsule-ownership-investigation.md.

Independent read-only review confirmed that unknown late-discovered capsules
cannot supply trusted extent information. Therefore neither current nbytes nor
destructor identity will authorize pointer reads. A public expm Python wrapper
alone is also inadequate: direct native entry points would bypass registration,
and replacing the callable changes observable identity/type.

## Runtime construction

1. Create a separate, pinned experimental runtime build; retain the current image
   and its evidence. Pin SciPy source archive, patch, compiler/toolchain and final
   wheel/image digests. Record the adaptation in judge manifests and reporting.
2. Instrument the actual native allocation-return sites, beginning with the
   expm/sqrtm shared module, rather than replacing public Python callables. Record
   storage identity, immutable capacity and ownership class at allocation time.
   Registration must precede exposure to candidate/test Python code.
3. Define registry lifetime and cleanup explicitly. Retain allocations only when
   graph arenas claim them, prevent identity/address reuse from rebinding old
   handles, and release metadata when native storage really dies. No unbounded
   permanent global registry or data-dependent candidate assistance.
4. Expose a fixed helper that accepts registered objects/opaque handles, never a
   transmitted address or destructor. Registration, inspection and bounded byte
   updates require explicit API validation. Candidate-side metadata remains
   untrusted by the receiver, whose own allocation/capacity checks are authoritative.
5. Verify installed binaries correspond to the patched source and run the original
   SciPy numeric/ownership controls. Keep arithmetic algorithms unchanged. Record
   instrumentation overhead and all observable runtime differences; do not claim
   an exact upstream reproduction if the build is adapted.

## Graph representation and transactions

6. Represent native allocation/capsule, root ndarray and derived views as separate
   handles. Wire state contains bounded bytes, capacity, ownership enum and array
   geometry; no pointer values, callable names or executable payloads.
   Preserve a capsule exported alone after its original root array dies. Source
   registration must retain enough immutable dtype/extent provenance for that
   case; a future receiver may keep a hidden root only to own the reconstructed
   capsule. When the source root is still live, record its handle so reconstruction
   binds that exact root and its `base` capsule, even if the graph references the
   capsule first. This relationship must be checked in both directions before
   commit, without trusting a sender-claimed pointer or size.
7. Validate dtype, total capacity, offsets, strides, overlap and all references
   before allocation. Freeze capacity and base relationships across calls. Views
   must retain the same actual root; exported capsules must be actual root bases.
8. Allocate through the fixed helper and register reconstructed storage. Populate
   aliases before applying final flags, with retained handle identity. Native
   storage writes must not temporarily make a readonly root writable.
9. Integrate native allocation into private graph rehearsal and live recapture.
   Test late root discovery, capsule-first export, geometry changes, detached
   aliases and readonly roots that still have writable preexisting views. Unknown
   ownership families stay explicit unsupported outcomes; no copied fallback.

## Required tests and admission

10. First failing controls must include all three currently failing Hamiltonian
    cases and direct native expm calls. Add shared/view/capsule identity, reverse
    mutation, retained readonly aliases, unknown/forged registration, invalid
    capacity/offset, duplicate owner claims and lifecycle/reuse negatives.
11. Verify snapshot and delta transports independently, complete full regression
    tests, and replay exact task116 in both suites with the adapted runtime identity.
    Keep before, intermediate and after outcomes; do not rewrite old image results.
12. Independently review native memory safety and ownership, then run a fresh
    uniform cohort and calibrate resource limits. This fixes transport only;
    task116's original oracle defects and full task review remain separate gates.

No stage permits guessing the extent of arbitrary foreign storage. Broader native
libraries require their own verified allocation registration or explicit capability
limitations. Completion of this refinement does not establish overall release
eligibility, provider fairness, or correctness of all upstream oracles.

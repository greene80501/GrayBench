# Experimental registered native storage

This directory is an **unadmitted runtime experiment**, not a scoring backend.
It instruments the two allocation-return sites in SciPy 1.18.1's matrix-function
module. It leaves arithmetic unchanged but changes allocation lifetime and
exposes additional native helpers. Results from this runtime must identify that
adaptation; they cannot be labelled unchanged upstream execution.

The patch verifies the exact C source digest before editing. The development
Dockerfile also verifies the source archive. Its apt and isolated Python build
dependencies are not locked yet, so it is not a reproducible release recipe.
The resulting image records installed Python packages, system packages and the
built wheel digest under `/native-build`.

The registry binds a capsule's exact identity to its allocation-time capacity.
It retains identities to prevent address reuse, and sweeps registry-only
capsules on subsequent registration. This delays destruction and can affect
peak memory. Graph-retained capsules have additional references and are not
swept. Experimental registry and transport bounds require calibration before
admission. The helper rejects changed capsule metadata before reading or writing
storage. It is not a defense against arbitrary native memory corruption within
the candidate process; the separate container remains the security boundary.

The experimental `_graybench_storage_new` factory allocates a zeroed 2D array
with a real registered capsule base for graph reconstruction. It accepts only
the four matrix-function numeric types and a capacity under the transport
limit. `_graybench_storage_descriptor` preserves the allocation-time dtype,
shape and extent even after an array changes shape or is collected.
`_graybench_storage_view` constructs bounded numeric aliases with their own
writable flag when the registered root is already readonly. It accepts no raw
address, checks the exact root identity, logical size and byte span, and rejects
object dtypes. The graph capsule/root/view codecs and private transition
rehearsal are experimental; the original pinned runtime does not include these
helpers and this image is not admitted for benchmark scoring.

Standalone checks run inside the experimental image, with this directory's
`tests` mounted read-only at `/checks`:

- `python /checks/check_registered_storage.py`: dtype/extent, readonly roots and
  writable aliases, exact-size writes, unknown DLPack capsules, sqrtm branches,
  and capsule identity retained after the root ndarray dies.
- `python /checks/check_capsule_metadata.py`: changed name, context, pointer and
  destructor must all reject inspection, reads and writes; restoration preserves
  the original bytes and foreign memory stays untouched.
- `python /checks/check_reentrant_cleanup.py`: a replacement destructor drops
  another allocation and recursively allocates during cleanup. Run in its own
  container because the regression can expose a native use-after-free.
- `check_registry_reentry_asan.py` with `registry_harness.c`: compiles the actual
  registry header under AddressSanitizer, then exercises nested cleanup. This
  caught a heap-use-after-free that ordinary successful numeric calls do not
  rule out. The harness is test-only and does not replace SciPy integration tests.
- `python /checks/check_registered_factory.py`: validates the receiving native
  allocation, exact bytes, readonly root with writable alias, and rejection of
  invalid type or allocation dimensions.

These checks do not establish graph transport fidelity. Native reconstruction,
capsule/root/view codecs, transaction validation, protected snapshot/delta
execution, full regression and reference replay remain required by the
[implementation plan](../../docs/superpowers/plans/2026-09-23-registered-native-storage.md).

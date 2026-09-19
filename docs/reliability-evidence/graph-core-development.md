# Experimental persistent object graph

This is implementation evidence for the [graph plan](../superpowers/plans/2026-09-19-call-object-graph.md),
not admission evidence for a benchmark campaign. Production candidate calls still
use the old value-only bridge and retain the [six identity defects](alias-boundary.md).
Release eligibility remains false.

## Container core

Commit `7ad270e` introduces persistent judge/candidate arenas, owner-prefixed object
IDs, shared positional/keyword roots, cycles, original-input return identity and
updates to detached earlier objects. All exported objects stay pinned for the
attempt; neither side traverses unpassed judge globals.

Incoming graphs are checked for session/sequence, ownership, duplicate/dangling
IDs, changed types, immutable-state rewrites and resource limits. Preparation
constructs private replacements without mutating existing objects. Commit applies
resolved fixed-codec updates; an unexpected apply failure closes the arena so the
oracle cannot continue with partially changed state.

The full Docker-enabled suite passed **469 tests** on 2026-09-19, including 33 new
graph cases. Local JUnit artifact: `outputs/GrayBench-v4-container-graph-full-tests.xml`.
These tests exercise the standalone arena, not an integrated v4 worker.

## Numeric storage implementation

The next development increment models an owning ndarray and its views as separate
graph nodes. Views refer to their actual owner, retaining dtype, byte offset,
shape, strides, writeability and alignment. A closed numeric C-type code is
recorded in addition to the dtype byte-width string: native Windows tests showed
that intc/int32 and uintc/uint32 can have equal storage strings but distinct scalar
classes. The code and declared storage width must agree on the receiving runtime. Storage bytes are sent once per owner;
returned view IDs resolve to existing local views. Numeric scalars preserve their
NumPy type and bytes, including signed zero and nonfinite values.

The schema rejects object/structured dtypes, out-of-bounds positive or negative
strides, inconsistent alignment flags, invalid base IDs, noncanonical bytes and
aggregate storage beyond the receiver's own limit before mutation. It preserves
the valid case of a writable view whose owner was subsequently marked readonly.
No physical-state normalization is performed.

The implementation uses NumPy's documented [buffer/offset/strides constructor](https://numpy.org/doc/2.2/reference/generated/numpy.ndarray.html)
and its [array interface](https://numpy.org/doc/2.2/reference/arrays.interface.html).
The [dtype character code](https://numpy.org/doc/2.2/reference/generated/numpy.dtype.char.html)
retains the built-in C-type distinction that the storage-width string alone loses.
Pinned-runtime tests verify overlapping slices, transposes, reversals, broadcasts,
empty arrays, endian bytes, retained aliases and malformed late updates.

Current unsupported forms are explicit: external buffers (including bytes and
memoryviews), ndarray subclasses, write-back temporary arrays, noncontiguous owning
arrays, dtype metadata/extended precision, and changes to an already exported array's dtype/shape/strides/base/offset.
These produce unsupported-interface errors instead of copied values. Geometry
updates and additional storage owners remain pending work, not a claim that all
NumPy behavior has been admitted.

Task 2 also still needs graph-aware scientific and primitive wrappers, including
their nested component aliases and symbolic coefficients. Circuit components,
persistent worker integration, exception-state transport, protected adversarial
replays and the full reference comparison are subsequent unfinished steps. Matrix
budgets for scientific/gate nodes are not yet exercised by this array-only registry.

## Verification of the numeric increment

The final Docker-enabled regression suite passed **504 tests** in 181.34 seconds
with no failures or skips. This includes 35 numeric graph cases and the 33 container
graph cases. Lint and formatting checks passed. Local JUnit artifact:
`outputs/GrayBench-v4-numeric-storage-typed-full-tests.xml`.

A separate trusted standalone probe passed eight checks inside the pinned Linux
image `sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`,
using Python 3.12.14, NumPy 2.2.4 and Qiskit 2.4.2. The probe ran with no network,
a read-only filesystem, unprivileged user and only five explicit source-module
mounts plus the trusted fixture. This was not candidate execution or a protected
oracle comparison. [Raw result](GrayBench-v4-numeric-storage-linux-probe.json)
SHA-256: `5e24d38dbcd0c14cc91a3573e4c0cf98ef4d839a81c72bf44387a05214d8f821`.

The result records hashes of the actual mounted source bytes and trusted probe.
These Windows working-tree files can have CRLF bytes differing from Git-normalized
LF blobs; the evidence does not silently substitute commit blob hashes. Earlier
469- and 498-test development results remain historical, before the subsequent
numeric type distinction correction. No model API generations were performed.

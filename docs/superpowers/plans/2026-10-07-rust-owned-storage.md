# Rust-owned storage implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Preserve Qiskit's actual Rust numeric allocation ownership in the protected graph transport without guessing extents or copying away aliases.

**Architecture:** Instrument the hash-pinned Rust NumPy allocation constructors before Python exposure. Private immutable metadata distinguishes initialized bytes from reserved bytes and identifies the exact owner and original root using a weak reference. Native inspection, reconstruction and alias helpers accept registered objects and bounded geometry, never addresses or destructors.

**Tech stack:** Python 3.12, Qiskit 2.4.2, Rust NumPy 0.28.0, PyO3 0.28, NumPy 2.2.4; separate experimental build.

**Spec:** [Registered native storage requirements](2026-09-23-registered-native-storage.md).

## Global constraints

- Retain stock environments and historical evidence; this is an adapted runtime.
- Read/write initialized bytes only; reserved Vec capacity is immutable provenance, not readable storage.
- Preserve actual `PySliceContainer`, root and view identities and lifetimes; unknown allocation types remain unsupported.
- Bound initialized and allocated storage to 16 MiB and geometry to 32 dimensions; reject overflow before allocation or pointer arithmetic.
- Keep arithmetic algorithms unchanged. No model calls or runtime qualification implied by host controls.
- No Docker repair, deletion, cleanup, restart or new Actions jobs in this work.

## Review focus

- A Vec with spare capacity must never expose uninitialized bytes.
- Owner-only export after root destruction must remain valid without a strong root retention cycle.
- Readonly root and retained writable aliases must keep their independent flags.
- Root data offset and negative/zero strides must be checked against initialized storage, not logical nbytes or reserved capacity.
- Spoofed owner names, object dtypes and excessive/overflowing geometry must fail before pointer access.

### Task 1: Instrument and test native storage

Files: `engine/native/patch_qiskit_rust.py`, `engine/native/rust_storage.rs`, `engine/native/tests/test_rust_storage.py`.

Interfaces: Qiskit `_accelerate` exports profile `rust-numpy-storage-v1`, exact owner type, descriptor/read/write/new/view helpers. Descriptor tuple is `(dtype_char, allocation_kind, initialized_bytes, allocated_bytes, origin_offset, root_or_none)`; new accepts `(dtype_char, kind, initialized_bytes, allocated_bytes, shape, strides, offset)`; view accepts `(registered_root, dtype, shape, strides, storage_offset)`.

- [x] Run native controls against stock Qiskit and record missing-helper failure.
- [x] Hash-check all modified upstream files before any write; instrument Box/Vec constructors and root exposure, retain upstream destructors.
- [ ] Compile a separate experiment, then build the actual Qiskit extension using its lock and patched NumPy dependency.
- [ ] Run native controls for spare capacity, all four numeric allocation types, Box/Vec, alias mutations, weak-root death, readonly aliases, bounded negative/empty/overlapping geometry and malicious inputs.
- [ ] Record source, patch, lock, toolchain, wheel/binary hashes and fresh read-only review. Host tests do not replace sanitizer or isolated release controls.

### Task 2: Integrate graph ownership

Files: a separate `engine/src/graybench/graph_rust.py`, numeric graph dispatch and registry, graph/native tests.

- [ ] Add failing round-trip and delta controls covering reciprocal owner/root links, owner-first/owner-only export, repeated retained aliases and late root discovery.
- [ ] Add strict wire codecs with initialized bytes distinct from allocated capacity, immutable origin offset and allocator kind, reciprocal references and exact runtime type anchors.
- [ ] Update numeric views to use registered Rust roots and fixed helper geometry; retain unsupported stock behavior.
- [ ] Run transactional, adversarial and native/protected controls with explicit adapted runtime identity.

### Task 3: Canonical replay and qualification

- [ ] Replay all 32 canonical task116 normal/hard cases; report intermediate and final outcomes without editing historical reports.
- [ ] Run complete regressions and a clean environment reproduction; independently review ownership and native memory safety.
- [ ] Run memory sanitizer and isolated adversarial controls, runtime/source binding and toolchain locking before qualification; Docker availability remains a separate prerequisite.
- [ ] Fresh uniform cohorts, independent task admission and benchmark validity remain separate release gates.

## Execution record

The user authorized autonomous implementation of the overhaul. Execute inline without another plan approval prompt. Source inspection confirms allocation constructors own typed buffers and preserve their destructors; stock task116's 32 numeric successes remain transport-unsupported. This plan does not weaken those failures into passes.

Task 1 is incomplete. Eight patch-process controls pass; 35 native controls are
written and collected but unrun. Windows Application Control blocked the generated
PyO3 build script before added-code type checking. No native build or graph
integration is claimed. Read-only source review found no actionable issue, which
does not substitute for compilation or runtime qualification. Preserve this
[source-only checkpoint](../../reliability-evidence/artifacts/rust-storage-source-2026-10-07/README.md)
and resume compilation in a permitted environment. Ruling: leave the active
engine unchanged until native ownership controls execute successfully; installing
uncompiled helper/codec support would hide the actual unsupported condition.

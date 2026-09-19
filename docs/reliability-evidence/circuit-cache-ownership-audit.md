# Native circuit-cache ownership audit

Eight assertions now reproduce the pinned Qiskit cache behavior on both Windows
and the Linux evaluator image. This audit changes the required circuit transport
design; it is not a graph implementation or a benchmark admission result.

- CircuitData copies input bit lists but retains its own exposed cache objects.
- Clearing instructions preserves membership caches.
- Adding a bit replaces the caches; old exported lists and dictionaries remain
  detached with their earlier contents.
- Replacing membership with equal-valued bits still changes cache identity.
- Neither replace_bits nor the readonly qubits property can adopt an existing list.
- Fixed native state restoration does not adopt an external index dictionary.
- A mutated public cache can differ from Rust membership. copy_empty_like()
  rebuilds membership getters from intrinsic data without repairing the original.
- find_bit returns the cached BitLocations object, including its shared nested
  registers list.

## Implementation consequence

The existing graph core allocates child shells independently and resolves all
references before commit. That cannot bind a new graph handle to a cache created
only when an existing native owner changes.

The [Task 3 refinement](../superpowers/plans/2026-09-19-call-object-graph.md)
specifies private rehearsal of the complete owner transition before live mutation,
then native cache creation/binding before immutable construction and ordinary
reference resolution. It includes detached-cache, equal-valued replacement,
malformed late update, duplicate-owner and placeholder regressions.

Late attachment of a previously exported ordinary list remains unresolved because
the verified SDK interfaces cannot adopt that object. It must fail explicitly
until a faithful implementation exists. This is a capability gap, not permission
to certify a narrower benchmark silently.

## Reproducible evidence

The fixture is engine/review/circuit_ownership_diagnostic.py. It executes only
trusted fixed SDK operations; no candidate code or pickle is executed. Both runs
use Python 3.12.14 and Qiskit 2.4.2. The Linux run uses image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd,
with the fixture mounted readonly, no network, user 65534, 512 MiB memory, one CPU,
64 PIDs and 16 MiB temporary storage. The reported probe hash was checked against
the actual mounted source bytes.

[Windows raw result](GrayBench-v4-circuit-cache-ownership-windows.json), SHA-256:
8418f25aa0e566bac993f893deb997b6a9139d6948fcd29456f9e3989dfbe34c.

[Linux raw result](GrayBench-v4-circuit-cache-ownership-linux.json), SHA-256:
d1709328c776f2de265ded2d026d54ec7353f58aa41219b895f03189d9d1ba93.

No runtime graph code changed in this increment, so the full 674-test result from
the preceding member-codec increment is retained rather than presented as a new
run. The new audit passed all eight assertions on each platform. No model
generations, certified scores or production v4 admission were produced.

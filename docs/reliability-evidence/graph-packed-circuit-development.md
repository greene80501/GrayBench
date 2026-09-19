# QuantumCircuit roots and packed standard operations

The standalone graph now transports exact QuantumCircuit roots, their actual
instance dictionaries, builder back-references and held QuantumCircuitData views.
Native CircuitData remains a separate owner node. Shared metadata, shallow copies,
detached old storage and replaced metadata dictionaries retain their identities.

Packed standard operations use a fixed SDK gate-enum map and intrinsic operand
positions. Parameters use the existing bounded expression schema; real parameter
vectors remain graph references. Labels, operation order and numeric global phase
are preserved. No decomposition or definition synthesis is performed. Retained
Python operation objects are explicitly rejected until their component graphs are
implemented; a standard-gate flag alone cannot establish packed ownership.

Owner finalization runs after ordinary graph components are resolved, then the
owner is re-encoded and compared with its declared state. The entire schedule is
rehearsed on private objects before touching live state. A regression exposed that
the native packed constructor accepts a complex RX parameter which the Python
operation wrapper later rejects. That rejection now becomes WireError during
private rehearsal, leaving the existing live circuit unchanged.

Register-addition coverage also exposed that replace_bits drops registrations.
Membership replacement now restores all declared registrations for that bit family,
while retaining the native cache identities and detached aliases required by the
wire graph. Independently removing registers without replacing membership remains
unsupported.

## Evidence

Eighteen new cases cover root/component aliases, shallow copies, packed gate
semantics and symbolic vectors, metadata replacement, native storage replacement,
register addition, labels, malformed streams and invalid native parameters.
The focused circuit and owner suite passed 35 tests. The complex-parameter test
was observed failing with an escaping CircuitError before the fix.

The full Docker-enabled suite passed **709 tests** in 195.92 seconds with no
failures, errors or skips. JUnit: outputs/GrayBench-v4-packed-circuit-full-tests.xml.
Ruff lint, 110-file formatting and secret-value diff checks passed.

The standalone Linux probe passed 23 checks in pinned image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
Seventeen dependency modules and the fixture were mounted readonly, with no
network, user 65534, 512 MiB memory, one CPU, 64 PIDs and 16 MiB temporary storage.
Reported source and fixture hashes were verified against actual mounted bytes.
[Raw result](GrayBench-v4-packed-circuit-linux-probe.json) SHA-256:
50d5adb29df2b70c8b889cc40e8575cbac887dbdc7d7c758c280e7c0d6fa749d.

This is development evidence, not production bridge admission. The worker still
uses v3. Remaining circuit capabilities include retained Python instructions,
nonstandard operations, symbolic phase, layouts, variables and anonymous-bit
identity. Task 3 remains active; protected v4 integration and its adversarial
acceptance checks remain required. No model generations or new cohort scores
were produced.

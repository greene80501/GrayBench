# Owned circuit members and native ownership findings

This increment starts Task 3 with standalone register-owned Qubit, Clbit and
AncillaQubit nodes, plus QuantumRegister, ClassicalRegister and AncillaRegister.
Equal-valued but distinct Python wrappers keep separate arena IDs; shared input
objects keep shared IDs. Alias registers retain ordered intrinsic member values,
without inventing Python aliases to the temporary wrappers returned by SDK getters.

Reconstruction uses a fixed family registry and the pinned SDK's owned-bit factory.
No callable, class path, reducer or constructor name is accepted from a payload.
Names must be bounded UTF-8 strings; register sizes are at most 512 and indices
must be valid exact integers. Fixed immutable records cannot be rewritten.
Anonymous bits, including anonymous members of alias registers, fail explicitly.

## Native findings that constrain the next work

The pinned SDK returns fresh QuantumCircuitData wrappers from circuit.data, but
each wrapper refers to the original circuit. Circuit qubits/clbits lists and their
internal index dictionaries are persistent Python objects. Register-list getters
return fresh lists/wrappers. Metadata is an actual shared dictionary.

For a packed built-in operation, repeated circuit.data[index] calls can produce
distinct Python operations. The same CircuitInstruction wrapper caches its own
operation getter. In contrast, append(operation, copy=False) retains the supplied
Python gate, including for RXGate. Both forms can report is_standard_gate=True,
so that flag alone cannot select the ownership representation.

Mutating the public qubits cache list does not change the internal bit count or
instruction operands. This divergence must be represented rather than repaired.
CircuitData's constructor and replace_bits both copy the supplied list; its qubits
property has no setter. Restoring an already-exported list as a later-discovered
CircuitData cache is therefore not solved by ordinary constructor replay. Circuit
cache allocation and late attachment require a separate explicit design.

Most importantly, Qubit._from_anonymous(uid) does not advance the global allocator.
Restoring the next ID and then creating a new Qubit produces two distinct objects
that compare equal. The trusted Linux probe reproduces this collision. Anonymous
identity transport needs a session-level solution; this increment does not silently
use the unsafe integer-ID restoration.

## Evidence

Twelve initial member tests failed before the codec; twenty focused cases now pass.
The full Docker-enabled suite passed **674 tests** in 187.93 seconds, with no
failures, errors or skips. Local JUnit artifact:
outputs/GrayBench-v4-owned-circuit-members-full-tests.xml. Lint, 103-file formatting
and secret-value diff checks passed.

The focused tests cover all three families, distinct equal wrappers, shared roots, ordered alias
registers, immutable rewrites, malformed late updates and explicit anonymous rejection.

The trusted standalone Linux probe passed 21 checks in the pinned image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
Thirteen dependency modules and the fixture were mounted read-only, without network,
as user 65534 with 512 MiB memory, one CPU, 64 PIDs and 16 MiB temporary storage.
All source and probe hashes were verified against actual mounted bytes.
[Raw result](GrayBench-v4-owned-circuit-members-linux-probe.json) SHA-256:
c84ae4b595826d164721dee71647d84f38ed13a8c24b577076d088c5742e427e.

## Remaining work

This is not QuantumCircuit or instruction graph support. Circuit caches, packed
versus Python instruction ownership, definitions, layouts, anonymous identities
and mutable circuit reconciliation remain unfinished. Production calls still use
the old bridge; its preserved identity verdict defects remain release blockers.
There were no model API generations or certified scores.

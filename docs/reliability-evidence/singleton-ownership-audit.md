# Singleton ownership and frozen-list audit

Eight native assertions pass on Windows and the pinned Linux runtime. Ordinary
copy, deepcopy and the SDK copy method all return the original singleton. A clone
allocated with object.__new__ retains its exact class and immutable API but is not
the object returned by XGate(). A shallow dictionary clone still shares parameter
storage and the raw cached definition, so it is not private validation storage.

Singleton immutability is not deep immutability. The actual instance dictionary
is mutable, and raw cached definitions can be mutable QuantumCircuits. Parameter
storage has the exact SDK _frozenlist type: ordinary append raises TypeError, while
an explicit list.append bypass can still change its contents. These observations
were checked in disposable processes and every global mutation was restored in a
finally block. An initial audit assumption that mutable CX's raw _params stayed
frozen was false: its raw list is ordinary list, while public params delegates to
the singleton base's frozen list. The corrected assertion passes on both systems.

## Implemented dependency

The graph now has a closed qiskit_frozen_list codec using that exact SDK type.
It preserves guard behavior, actual list identity, shared children, cycles and
explicit base-list mutations. Fixed base-list updates apply prepared values after
validation; no payload-supplied methods or arbitrary subclasses are invoked.
Instruction raw parameter fields accept this exact graph kind as well as plain
lists. Five focused tests pass after four initial unsupported-type failures.

This is not singleton gate support. Returning a cloned singleton would fail native
factory identity; returning the live factory object during prepare could mutate
SDK globals before validation completes. These alternatives are explicitly not
accepted as implementations.

## Next owner-allocation requirements

Extend the owner transition design to distinguish private rehearsal objects from
live factory-bound objects. Preserve actual singleton dictionaries, frozen parameter
lists and raw definition aliases, including equal-valued replacements. Bind only
explicitly exported graph components; do not copy private judge globals or RNG.
Use separate receiver processes when testing factory identity so a shared Python
interpreter cannot accidentally make sender and receiver share the same singleton.
Before admission, verify factory identity, held-child aliases, malformed-update
atomicity, raw definition updates, shared controlled-X bases and stale preparation
handling. Initial factory-child binding versus replacement must be resolved
explicitly; matching objects merely by equal values is insufficient.

## Evidence

Fixture: engine/review/singleton_ownership_diagnostic.py, SHA-256:
b9792196ba0f6a871eff9378091a1233ca2189976ffc50530c50f1fa61d3f4f0.

[Windows audit](GrayBench-singleton-ownership-windows.json), eight checks,
SHA-256: b0f5ebb288ff2b4714d626ad21666fcadc429fd3226735260be9626329dbdb18.

[Linux audit](GrayBench-singleton-ownership-linux.json), eight checks,
SHA-256: 39660b75a57d13b11e49bcda662d188001cdf3f77fc097ba34076a741044cdc8.

The standalone graph probe passes 27 checks with nineteen source modules and
fixture hashes verified against actual mounted bytes.
[Graph raw result](GrayBench-v4-frozen-list-linux-probe.json), SHA-256:
65389b695e051d4178d8e30ab237294cdc212a042ee4b18c2edbb68c6191ca9e.
Both Linux fixtures ran readonly without network as uid 65534, with 512 MiB memory,
one CPU, 64 PIDs and 16 MiB tmpfs in image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.

The full Docker-enabled suite passed **748 tests** in 193.94 seconds with no
failures, errors or skips. JUnit: outputs/GrayBench-v4-frozen-list-full-tests.xml.
Ruff lint, 117-file formatting and secret-value diff checks passed.

The production bridge remains v3. No new model generations, reference cohort
aggregate or certified score was produced. Task3 remains active.

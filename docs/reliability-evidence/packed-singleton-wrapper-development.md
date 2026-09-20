# Packed singleton wrapper references

Anchor-enabled graph traversal now follows stable exact-type singleton operation
wrappers returned by native CircuitData. These wrappers use the retained-operation
record, keeping actual object/component references separate from cached native
name, label, parameters, widths and standard/Python representation. Two distinct
singleton clones remain distinct, while repeated references to a public factory
bind to the same receiver factory.

The first two regressions failed before implementation: exporting only a circuit
omitted its reachable XGate state, and reconstructing a circuit replaced a retained
private singleton clone. Seven new tests now cover those cases, repeated wrappers
for H/CX/CCX/SWAP, and a circuit-only round trip that updates the original factory
and preserves detached metadata aliases. Together with existing anchor, bootstrap
and controlled cases, 65 focused tests pass.

Traversal carries a trusted singleton_refs mode from the explicit anchor-enabled
arena through local current-state capture and canonical native-owner checking.
This is not a peer-controlled wire flag. The frozen public bootstrap and ordinary
non-anchor graph mode retain their previous formats. The latter is not full
singleton admission and is not a fallback for the future protected anchor protocol.

Fresh independent-process probes pass on Windows and the pinned Linux image for
three profiles: public X factory, manually allocated exact-type X clone, and an
immutable CX retained in native Python form because its base was labeled at
insertion. Each sends only a circuit root, checks preparation leaves live factory
state untouched, verifies shared wrapper identity and separate cached label/mode,
then changes the wrapper and replaces metadata before returning it to the origin.
The origin verifies original circuit/wrapper identity and detached child aliases.
Factory/clone profiles export37 nodes; the controlled profile exports46.

Raw artifacts (22 source files and fixture hashes verified against mounted bytes):

- Windows: GrayBench-packed-singleton-wrapper-windows.json
  SHA-256 51bd3e398b86287f170cb60bdefd3f23e319e452688c89b3b6a5961567793cd0
- Linux: GrayBench-packed-singleton-wrapper-linux.json
  SHA-256 8845c866ced6b079ae29d8cfb17afa0688f5e18e949f220f752b8c6b367d7038

Linux uses the pinned Qiskit2.4.2/Python3.12.14 image, no network, read-only filesystem,
unprivileged UID, 512MiB, one CPU, 64PIDs, 16MiB tmpfs and one OpenBLAS thread.
Only explicit implementation modules and the trusted fixture are mounted; no
candidate, credentials or private judge material is present.

This closes the stable singleton-wrapper gap documented in anchor-transfer-development.md.
It does not complete standalone CircuitInstruction or other remaining interfaces,
production worker/bootstrap integration, protected counterexamples, reference-cohort
admission or provider calibration. No model generations or new benchmark scores
were produced. Prior evidence remains unchanged.

Final Docker-enabled suite: 800 passed in 251.90 seconds. JUnit confirms zero
failures, errors or skips in outputs/GrayBench-v4-packed-singleton-wrapper-full-tests.xml.
Lint, formatting, diff whitespace and secret-value checks pass.

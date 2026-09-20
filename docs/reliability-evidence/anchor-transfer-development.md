# Explicit public-anchor graph transfers

GraphArena now offers an explicit anchors=PublicAnchorRegistry argument and a
separate call_graph_anchors_v1 envelope. Each exported node declares its original
public anchor key or null; the peer verifies the frozen registry manifest, exact
schemas, known key and kind, unique claims, and stable claims on existing handles.
A fixed singleton codec preserves actual instance dictionaries and component refs.
It allocates private shells; public identity comes only from verified live binding.
A graph arena without the registry rejects singleton/anchor transfer.

Incoming transfers build a local-only closure of the receiver's currently bound
objects. This is necessary because a frozen bootstrap alone cannot describe later
local mutations. Private reconstruction rehearses the whole transition with the
actual initial native-owner state. Supplemental b: handles exist only in rehearsal;
only exported objects are applied live. A precommit state-and-identity comparison
rejects intervening changes, including equal-valued replacements. Neither the full
public registry nor unpassed factory state is transmitted or reset.

Twenty-three new tests run with independent sender and receiver Python processes.
The first nine failed on the missing anchor interface before implementation.
Coverage includes all 30 fixed factories, actual dictionary/params/definition/cache
aliases, equal replacements, child-before-owner export, detached aliases across a
round trip, mutable controlled gates sharing singleton bases, malformed manifests,
unknown/duplicate/type-incompatible/changed anchor claims, stale live state,
nonfactory clones, explicit protocol negotiation and late native-owner rejection.
A metadata-only export is verified to contain one node.

The combined independent-process probe found an additional reconstruction bug:
a controlled instruction inserted before a shared base label changed must retain
its earlier native standard/Python representation. Three label-transition cases
failed before the fix. Qiskit's pinned OperationFromPython implementation selects
native standard controlled gates using both closed controls and an unlabeled base:
https://github.com/Qiskit/qiskit/blob/2.4.2/crates/circuit/src/circuit_instruction.rs#L607-L643
Reconstruction now uses the fixed native enum's name/control width and a temporary
base label to select the declared cached representation. It restores all actual
dictionaries in finally; it does not normalize the user's current gate state.

The final standalone probe passes six checks in independent processes on Windows
and in the pinned Linux image. Its round trip exports 46 nodes, preserves native
controlled instruction ownership and factory identity, rejects a late malformed
owner before mutation, and preserves receiver-only HGate state. It mounts 22 explicit
source modules plus the trusted fixture, with no network, read-only filesystem,
unprivileged UID, 512 MiB memory, one CPU and 64 PID limits. OpenBLAS threads are
limited to one for these subprocess probes. All source and probe hashes were
verified against the actual mounted bytes.

- Windows: GrayBench-anchor-transfer-windows.json
  SHA-256 d1ec6d45b43d3fc2d81f975eb4c6cea3923f4838b221ff67841178454c5b25ed
- Linux: GrayBench-anchor-transfer-linux.json
  SHA-256 0819d5fb326baad8640aec7ed51ba724744e671c9848b8fa1a8865d73c4b4032

The earlier 790-test full run preceded the additional label regressions/fix and is
retained as intermediate evidence. It does not verify the final implementation.

This remains a standalone graph API, not production protected-call integration.
Before-user-code bootstrap, other circuit/instruction interfaces and both full
reference cohorts remain unfinished. Packed immutable operation wrappers still
need explicit ownership review: this milestone verifies directly exported singleton
objects and bases of retained mutable operations, not every singleton reachable
through an otherwise packed instruction. No model generations or new model scores
were produced, and no claim of complete benchmark fairness is made.

A fresh Windows native observation confirms the remaining packed-wrapper concern:
a circuit built with qc.x(0) returns the public XGate() from data[0].operation and
reads subsequent changes to that factory's raw label. The current packed-only
snapshot includes zero singleton nodes for that circuit. Native CircuitData can
retain a manually allocated exact-type singleton clone, so explicit wrapper refs
have a feasible private-allocation path. This observation sets the next regression
and implementation target; it is not completed cross-platform wrapper admission.

Final Docker-enabled suite: 793 passed in 277.72 seconds; JUnit confirms zero
failures, errors or skips (outputs/GrayBench-v4-anchor-transfer-final-tests.xml).
The focused anchor/controlled tests passed36 cases; formatting120 files, lint,
whitespace and secret-value checks pass. The final full run includes the native
enum-based reconstruction fix and all23 new independent-process tests.

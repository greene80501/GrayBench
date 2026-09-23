# Persistent Call Object Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace value-only cross-container calls with a bounded reference graph that preserves admitted identity and mutation semantics.

**Architecture:** A persistent arena in each container owns stable reference IDs. Fixed type codecs validate graph snapshots before atomic reconciliation; the host only forwards bounded bytes. Old v3 evidence remains distinct from the new protocol.

**Tech Stack:** Python 3.12, pinned Qiskit 2.4.2, NumPy, existing immutable Docker image and pytest.

**Spec:** [Persistent call object graph design](../specs/2026-09-19-call-object-graph.md).

## Global Constraints

- Private tests, references, judge globals and RNG state never enter the candidate container.
- No pickle, arbitrary imports/constructors/attribute names, executable reconstruction payloads or host execution of candidate data.
- Keep Python 3.12 and the current pinned runtime; do not use an SDK upgrade to mask semantics changes.
- Preserve at most 100,000 nodes per arena and 100,000 edges per snapshot, plus existing message/depth/array/matrix limits.
- Unsupported graph types never silently fall back to value-only snapshots.
- Primitive scalar identity, weak-reference/finalizer/garbage-collection observations remain outside the admitted contract.
- Freeze protocol version, graph registry digest, source/image and limits in manifests; never reinterpret old v3 evidence.
- Keep overall release eligibility false until the broader admission and reproducibility gates pass.

## Review Focus

- Shared objects across positional/keyword boundaries: represented by one node (Task 1).
- Equal-valued replacements and detached children: preserve distinct IDs and synchronize retained objects (Tasks 1 and 4).
- Shared NumPy views and held circuit metadata: preserve shared storage/object identity (Tasks 2 and 3).
- Malicious references, immutable-node rewrites and late validation failures: reject before mutation (Tasks 1 and 5).
- Mutate-then-raise and cross-call retained state: match native observable behavior without leaking private globals (Tasks 4 and 5).

## File and interface map

Create `engine/src/graybench/graph_wire.py` for schema validation, resource budgets and arenas.
Create `engine/src/graybench/graph_types.py` for the closed type registry and container codecs.
Create `engine/src/graybench/graph_numeric.py` for numeric storage and scientific/primitive state.
Create `engine/src/graybench/graph_circuit.py` for Qiskit circuit/instruction component state.
The registry references fixed local handlers, never names supplied by candidates.

Public arena API shared by all tasks:

```python
class GraphArena:
    def __init__(self, *, side: str, session: str, limits: GraphLimits): ...
    def snapshot(self, roots: dict[str, object], *, sequence: int) -> dict: ...
    def prepare(self, snapshot: dict, *, sequence: int) -> PreparedGraph: ...
    def commit(self, prepared: PreparedGraph) -> dict[str, object]: ...
    def close(self) -> None: ...
```

`GraphLimits` is a frozen dataclass with nodes=100000, edges=100000,
message_bytes=1048576, array_bytes=524288, matrix_bytes=524288, depth=32.
Callers pass their existing configured message limit rather than silently using a
different cap. `PreparedGraph` is an internal validated plan bound to its arena,
session and expected sequence; it is not wire data and cannot be accepted from JSON.
Preparation allocates only private staging nodes and does not mutate existing objects.

A fixed `NodeCodec` registry entry defines `kind`, `matches(object)`,
`state(object, ref)`, `validate(state, shape_index)`, `allocate(state, shape_index)`,
`populate(object, state, resolve)`, `tokens(state)` and `apply(object, prepared)`.
`ref(object)` returns a scalar or exact `{ref: id}` record; `resolve(id)` returns
only an already validated/allocated graph object. `shape_index` contains validated
node kinds and structural dimensions, not arbitrary object access. These interfaces
are implemented in Task 1 and extended explicitly in Tasks 2 and 3. Population
constructs a private prepared value; apply consumes already resolved values and
does not parse wire data. Complete validation precedes any apply call.

Run all commands below from `work/GrayBench/engine`; use `uv run --extra qiskit
--extra dataset pytest ...`. Format before source-bound protected replays.

### Task 1: Container graph, arenas and transactional validation

Files: create `graph_wire.py`, `graph_types.py`, `tests/test_graph_wire.py`.
Produces the arena/codec interfaces above, with list/tuple/dict/PropertySet support.
Do not route production candidate calls through the new arena yet.

- [x] Write the shared-reference regression and observe failure on the old codec:

```python
def test_shared_positional_keyword_object():
    shared = []
    roots = {"args": (shared,), "kwargs": {"b": shared}}
    sender = GraphArena(side="judge", session="test", limits=GraphLimits())
    receiver = GraphArena(side="candidate", session="test", limits=GraphLimits())
    actual = receiver.commit(receiver.prepare(sender.snapshot(roots, sequence=1), sequence=1))
    assert actual["args"][0] is actual["kwargs"]["b"]
```

- [x] Implement traversal with strong-reference ID maps, exact schemas and fixed
  ownership prefixes. Allocate mutable shells first, build tuple dependencies,
  then populate mutable containers. Charge nodes/edges/bytes across the entire arena.
- [x] Test a self-referential list, mutual list/dict cycle, tuple containing a list
  pointing back to that tuple, ordered mappings and PropertySet missing-key behavior.
- [x] Test equal-valued distinct objects remain distinct, replacements get new IDs,
  and an existing immutable tuple ID cannot acquire a different state.
- [x] Add a failed-preparation test: existing list `[1]`, malformed later reference;
  `prepare` raises WireError and the list remains `[1]`. Repeat with duplicate IDs,
  dangling references, unknown kinds, foreign sessions, stale sequence, boolean IDs,
  invalid ownership and structural/byte-limit exhaustion.
- [x] Add a second snapshot retaining an old detached child; mutations of that child
  must update its original receiver object even when it is no longer in current roots.
- [x] Run focused tests and lint, inspect validation and ownership, commit. Per-task
  review is superseded by the executing-plans workflow: one whole-plan review
  after Task 5. Docker-enabled suite: 469 passed on 2026-09-19; 33 new graph cases.
  This standalone module is not yet integrated into production candidate calls.

### Task 2: Numeric storage and scientific/primitive object ownership

Standalone component implementation complete: ndarray owner/view and typed NumPy scalar nodes implemented and
locally tested. Scientific and primitive wrappers now have component graphs;
Numeric SparsePauliOp/CNOTDihedral component graphs are also implemented;
Parameter/vector/element and UUID identities are implemented in graph_symbolic.py;
bounded expression replay and reference-slot symbolic arrays are also implemented.
Array metadata updates now preserve byte count, base and offset. Storage resizing,
external buffers and other documented unsupported forms remain explicit failures.
Task 2 is complete within that bounded contract; production admission is still pending.


Files: create `graph_numeric.py`, `graph_scientific.py`, `graph_primitive.py` and
corresponding tests, plus graph_symbolic.py and its tests; modify `graph_types.py` and arena resource accounting. The
separate modules keep numeric storage, scientific state and primitive field rules
independently readable. Instance dictionaries are explicit graph nodes with fixed
field validation, not opaque copies or arbitrary attribute updates.
Consumes Task 1's fixed NodeCodec contract and arena references. Produces graph-aware
numeric/scientific/primitive handlers with explicit rejection of unsupported forms.

- [x] Write native/graph shared-storage tests before handlers:

```python
def test_numpy_views_keep_shared_storage(graph_roundtrip):
    backing = np.arange(12, dtype=np.float64)
    left, right = graph_roundtrip((backing[1:8], backing[3:10]))
    left[2] = 91
    assert right[0] == 91
    assert np.shares_memory(left, right)
```

  Define `graph_roundtrip` in the test fixture using the two arenas and
  snapshot/prepare/commit sequence from Task 1.
- [x] Represent owning numeric buffers and array views with validated dtype, offset,
  shape, strides and writeability. Validate min/max byte addresses for positive,
  negative and zero strides before allocation. Numeric byte buffers never use object/structured dtypes. The separate
  graph_object_arrays codec uses graph reference slots, never object-pointer bytes.
- [x] Test disjoint equal arrays stay disjoint, overlapping slices, transposes,
  negative strides, read-only views, endian preservation and nonfinite numeric bytes.
- [x] Map Statevector/DensityMatrix/Operator/Choi, ScalarOp/SparsePauliOp,
  Clifford/StabilizerState/CNOTDihedral and BitArray/DataBin/PrimitiveResult/
  PubResult/SamplerPubResult to explicit component references. Reuse existing numeric
  field validation, not opaque deep copies. Every existing tree-supported type gets
  either a graph handler or an explicit unsupported capability entry.
- [x] Test two wrapper objects sharing one numeric array, repeated DataBin fields,
  metadata shared with a separate argument, and a symbolic coefficient shared by
  multiple operators. Test inconsistent dimensions/state and reserved DataBin fields.
- [x] Run focused tests, review memory/ownership validation, commit.
  Final Docker suite: 654 passed; standalone pinned Linux probe: 18 checks passed.
  Fresh whole-plan review remains after Task 5 as previously ruled.

### Task 3: Qiskit circuit and instruction component graphs

In progress: owned bit/register members now have standalone graph codecs. Native
packed/Python instruction and CircuitData cache findings are recorded in
[member development evidence](../../reliability-evidence/graph-owned-circuit-members-development.md).
Anonymous bit identity and circuit-cache attachment remain explicit open design work.

Files: create `graph_circuit.py`, `tests/test_graph_circuit.py`; modify `graph_types.py`.
Consumes Tasks 1/2. Produces graph-aware handlers for current circuit/instruction
families; new control-flow support remains a separate codec requirement.

- [ ] Record native pinned-SDK identity behavior for registers/bits, circuit data
  wrappers, instruction copies, parameters, cached definitions and metadata. Turn
  each supported relation into a graph round-trip or update assertion.
- [x] Write the held-metadata/returned-root regression:

```python
def test_circuit_update_keeps_existing_root_and_metadata(graph_exchange):
    circuit = QuantumCircuit(2)
    metadata = circuit.metadata
    def change(remote):
        remote.x(1)
        remote.metadata["changed"] = True
        return remote
    result = graph_exchange(change, circuit)
    assert result is circuit
    assert circuit.metadata is metadata
    assert metadata["changed"] is True
    assert circuit.count_ops() == {"x": 1}
```

  Implement `graph_exchange` as two persistent arenas: send inputs, invoke trusted
  fixture, snapshot result plus all exported state, prepare/commit at the sender.
- [ ] Encode registers/bits, metadata/layout, mutable instruction parameters, base
  gates and raw cached definitions as component references. Preserve open controls;
  never trigger lazy synthesis while serializing state.
- [ ] Implement fixed in-place updates with prevalidated structure. No payload-defined
  attribute assignment, whole-object replacement or indiscriminate `__dict__.update`.
- [ ] Test two circuits sharing admitted components, duplicate circuit arguments,
  held metadata/definition/instruction aliases, equal-valued replacements, removal of
  operations, added bits/registers and parameters reused in nested definitions.
- [ ] Preserve/reject alias relations at every component boundary explicitly; do not
  claim support by copying an opaque `circuit_v5` leaf.
- [ ] Run existing circuit/controlled/numeric tests plus new graph tests, review and commit.

### Task 3 implementation refinement: owner-created cache objects

This refines Task 3 after the native ownership audit; it does not replace Tasks
3-5 or relax the spec's identity and validate-before-mutate requirements.
The current independently allocated child shells cannot represent newly generated
Rust-owned caches. Complete these steps before claiming circuit mutation support.

Files: create engine/src/graybench/graph_owned.py and
engine/tests/test_graph_owned.py; modify graph_wire.py, graph_circuit.py and
the circuit regression tests. Keep runtime code separate from the audit fixture.
The existing whole-plan review remains after Task 5.

**Fixed interfaces and execution order**

The implemented internal frozen OwnedCommitPlan in graph_owned.py contains
records, previous_records and roots. These are private copies of schema-validated
graph data, not payload-selected actions. A separate per-owner record is
unnecessary: fixed codecs expose transition_owner(value, previous, desired, index)
and owner_children(value, state). CircuitData cache slots are a fixed local mapping
for qubits, clbits, qubit_indices and clbit_indices.

The graph_owned module exposes the actual implemented signatures:
- rehearse(records, previous_records, roots, materialize) -> OwnedCommitPlan
- execute_owned(plan, existing_objects, materialize) -> (objects, resolved_roots)

materialize is the arena's bound private construction method, carrying its limits;
no callback is accepted from wire data. Rehearsal reconstructs the previous graph
privately, then executes the complete next transition including SDK calls, cache
binding, immutable construction and regular updates. Canonical owner re-encoding
rejects reconstruction that changes declared state. All objects come only from
exported records; no private globals or unpassed objects are enumerated.

The foundation now supports CircuitData membership, BitLocations, exact
QuantumCircuit roots and packed standard operation streams. Python component
codecs live in graph_quantum_circuit.py; fixed packed operations live in
graph_packed.py. Owner cache claims use owned_tokens separately from ordinary
parameter references; finalize_owner installs operations after graph resolution.
Basic mutable retained Python instructions now have graph_instruction.py component
codecs and graph_python_ops.py native-cache records. Shared definitions and
parameter lists are preserved without lazy synthesis. Exact cached native qubit/clbit arities are read through
DAGOpNode.from_instruction and preserved separately from the current operation. Controlled components and native-role transitions now have standalone coverage.
Singleton instructions, symbolic phase, variables, layouts,
anonymous identities and late attachment remain incomplete. The regressions below
remain requirements for the full circuit layer, even where its native owner
already has corresponding passing tests.

The live commit executes the already validated schedule in this order:
1. Allocate ordinary mutable shells and new native owner shells.
2. Apply intrinsic owner membership transitions using fixed SDK methods.
3. Read owner-created caches through fixed getters and bind their graph handles.
   An existing handle must still designate its original Python object. Reject a
   newly discovered owner claiming an already-exported unattached list/map during
   rehearsal: the SDK cannot adopt that object through the verified API.
4. Resolve new immutable nodes (including tuples and BitLocations) using the
   bound children; then prepare/apply regular container and Python-object updates.
   This can preserve cached contents that differ from intrinsic membership.
5. Apply operation/global-phase state after Python operation objects are ready.
   Verify that this did not unexpectedly invalidate the bound membership caches.
6. Resolve return roots from the final handle map and install the graph history.

New immutable nodes and new containers must not retain pre-binding placeholders.
No existing immutable node or child ID may be rebound. Retain detached prior
caches in the arena exactly like detached ordinary lists. A live execution failure
closes the arena and is never interpreted as a wrong model answer.

PreparedGraph binds this internal plan to arena identity, generation and sequence,
as it already does for ordinary updates. Keep the current path for codecs without
native-owned children until both paths have equivalent adversarial coverage.
No v3 fallback is permitted.

**Required regression sequence**

- [ ] Write and run the initial shared-cache regression (expected unsupported
  before implementation):

    def test_circuit_and_held_cache_have_one_receiver_object():
        circuit = QuantumCircuit(2)
        remote, cache = graph_roundtrip((circuit, circuit.qubits))
        assert remote.qubits is cache

  graph_roundtrip uses two GraphArena instances and snapshot/prepare/commit,
  exactly as the existing member test helper does.

- [ ] Implement fresh-owner cache binding and assert aliases inside a returned
  tuple and nested dictionary resolve to the actual owner-created list.
- [ ] Add the existing-owner mutation regression:

    def test_add_bit_retains_detached_old_cache():
        circuit = QuantumCircuit(2)
        old = circuit.qubits
        remote, held = graph_roundtrip((circuit, old))
        remote.add_register(QuantumRegister(1, "extra"))
        graph_return(remote)
        assert circuit.qubits is not old
        assert len(old) == len(held) == 2
        assert circuit.num_qubits == 3

  graph_return reverses the same two persistent arenas at response sequence 1;
  it must return the original circuit object.
- [ ] Add same-valued replace_bits: it must create new cache IDs even when all
  member values compare equal. Old cached dictionaries and their BitLocations
  register lists must remain reachable and unchanged through old aliases.
- [ ] Add cache-content divergence: pop from the public qubits list, retain
  num_qubits and actual operation membership, round-trip, and verify both states.
- [ ] Add a late dangling reference after an otherwise valid add-bit transition.
  prepare must fail while the existing live circuit, cache identities, cached
  contents, operations and private global state remain unchanged.
- [ ] Add a new tuple referencing a new cache and a detached tuple referencing the
  old cache. Neither may contain a placeholder list after commit.
- [ ] Add two owners claiming one distinct cache handle and reject before mutation.
  Add an already-exported list followed by its previously unexported CircuitData
  owner: reject explicitly while late-attachment support remains unavailable.
- [ ] Run all graph tests, the full Docker-enabled suite, and a new exclusive
  source-bound Linux fixture exercising the same transitions. Only then connect
  this machinery to the remaining circuit/instruction work above.

Known limits are capabilities, not final-goal exclusions. Anonymous bit equality,
late cache attachment and any unsupported native ownership form still require
resolution or task-specific admission evidence before release. No benchmark score
becomes certified merely because this implementation refinement passes.

### Task 4: Persistent v4 call lifecycle and exception state

Files: modify `worker.py`, `sandbox.py`, `upstream.py`, `upstream_process.py`,
`judge.py`, `provenance.py` and their explicit mounted-file/source manifests;
create `tests/test_graph_bridge.py`.
Consumes the completed arena and type registry. Produces a separately identified
v4 candidate/protected-judge call path with no implicit v3 fallback.

- [x] Translate the six preserved diagnostic fixtures into protected regression tests
  with native expected outcomes: five passes and one failure, never the old outcomes.
- [x] Initialize one arena per candidate/oracle attempt and synchronize every exported
  mutable node, not just nodes reachable from the latest arguments. Host orchestration
  forwards validated envelope bytes and never reconstructs candidate graph objects.
- [x] Replace separately encoded value/args/kwargs fields with one graph envelope and
  exact root validation. Returned input IDs resolve to original judge objects.
- [x] Add a retained-input test where call two mutates an object supplied in call one
  but absent from call two's arguments. Verify mutation through an old judge alias.
- [x] Add mutate-then-raise behavior:

```python
def candidate(values):
    values.append(2)
    raise ValueError("expected")

def check(proxy):
    values = [1]
    with pytest.raises(ValueError, match="expected"):
        proxy(values)
    assert values == [1, 2]
```

  In protected test source use ordinary try/except/assert rather than importing pytest.
- [x] Add a fixed inert exception allowlist and distinguish returned, raised,
  codec/runtime failure envelopes. Apply validated preceding mutations before raising
  the admitted exception in the oracle. Unknown exceptions remain unsupported.
- [ ] Preserve startup handshake, pause/resume boundaries, active-time accounting,
  byte limits, discard-result behavior and runtime/error classifications.
  Core regressions pass at 3ed07d2. Still open: unexpected bridge exceptions can
  be swallowed by test code, and configured graph/transport limits need a complete
  audit. Three new fault-injection regressions reproduce the false-pass gap.
- [ ] Freeze v4/registry identity in configuration and campaign resume. Reject protocol
  mismatch before dispatch, and retain a clearly identified historical v3 path only
  for source-specific replay, not automatic scoring fallback.
- [ ] Run protected bridge tests and existing sandbox/recipe/campaign tests, review and commit.

### Task 5: Adversarial admission and full reference comparison

Files: extend `tests/test_graph_bridge.py`, add source-bound evidence runner under
`engine/review/`, update docs/reliability-evidence and protocol documentation.
Consumes v4 integration. Produces auditable admission evidence with remaining blockers.

- [ ] Attempt duplicate/foreign IDs, changes to an existing ID's class, references to
  unexported judge objects, over-limit cycles, nested buffer abuse and malformed late
  updates. Verify rejection before existing judge state changes.
- [ ] Verify mounts still exclude private tests, references, credentials and Docker
  socket from the candidate. No graph field authorizes a host constructor or code path.
- [x] Replay tasks50/63/72/73/147 on both pinned suites; record control-flow/RNG/oracle
  limitations separately. Never copy the private test's seeded RNG into the candidate.
- [ ] Run the full regression suite with Docker and one exclusive source-bound offline
  reference scan per suite. Compare previously passing task outcomes to the preserved
  baseline; investigate every regression before making compatibility claims.
- [ ] Record the six diagnostic native/bridge outcomes, graph/registry/source/image
  identities, malformed-payload evidence, runtime limits and unresolved capabilities.
- [ ] Update PR under the user's identity, attach it, and leave overall release
  eligibility false until all unrelated benchmark requirements are verified.

## Self-review and execution state

The ten spec invariants map to Tasks1Ã¢â‚¬â€œ5: identity/topology/validation (1), storage
and nested ownership (2Ã¢â‚¬â€œ3), persistent calls/exceptions/privacy (4), and adversarial
plus real-cohort evidence (5). All five review-focus cases have explicit tests.
This plan does not claim implementation completion or user review of this artifact.
Continue inline under the existing goal authorization; no parallel implementation
is required. Each task's source-bound evidence uses a new exclusive output path.


### Task3 refinement: controlled objects and native representation

The eight-check Windows/Linux audit in
[controlled ownership evidence](../../reliability-evidence/controlled-ownership-audit.md)
shows that current control state does not identify the stored native representation.
An existing open CRX can remain a native Python operation after being closed;
an existing closed CRX can remain native standard after being opened. Public params
delegate to the actual base gate while raw _params remains independent.

- [x] Add fixed controlled component schemas and regressions for shared base gates,
  public/raw parameter lists, raw definitions and current control fields.
- [x] Record native standard/Python representation explicitly and verify it in
  canonical reconstruction. Do not infer it from the current Python control state.
- [x] Preserve both open-to-closed and closed-to-open cache transitions, restoring
  every temporary base/controlled dictionary on success or exception.
- [ ] Resolve exact singleton base ownership before admitting controlled X families.

This refines Task3; Task4/5 and the full benchmark requirements remain unchanged.


### Task3 refinement: singleton allocation phases

The [singleton audit](../../reliability-evidence/singleton-ownership-audit.md)
confirms that ordinary copying cannot create private staging objects, while a
manually allocated clone cannot satisfy SDK factory identity. Raw dictionaries and
cached definitions remain mutable despite the singleton's guarded setters.

- [x] Implement exact _frozenlist graph nodes, preserving public guards and explicit
  base-list updates, plus instruction parameter references to that kind.
- [x] Separate private singleton rehearsal from live fixed-factory binding in the
  owner commit machinery. Preparation must not mutate the process's real singleton.
- [x] Resolve initial binding of factory-owned children versus equal-valued
  replacement explicitly; preserve dictionary, frozen-list and definition aliases.
- [x] Verify factory identity and malformed-update atomicity in separate processes,
  then cover shared singleton bases in controlled X families.

These requirements refine the existing owner transition plan. They do not permit
copying private judge globals or narrowing the remaining benchmark objective.


### Task3 refinement: fixed public anchor registry

The [fresh-process capture](../../reliability-evidence/singleton-anchor-capture.md)
produced identical 30-factory/676-object graphs in two Windows processes and two
pinned Linux containers. Equal-valued replacement is distinguishable only if the
original identity registry remains frozen for the session.

- [ ] Bootstrap a versioned fixed public SDK anchor registry before candidate/test
  user code; keep strong original-object references and a verified layout hash.
- [x] Add strictly validated anchor metadata only to actually exported nodes;
  reject unknown, duplicate, incompatible or changed anchor claims.
- [x] Rehearse with private cloned anchor objects; bind live commit to actual
  receiver factory objects. Supply explicit initial state for newly bound native
  owners instead of pretending they have prior exported records.
- [x] Cover original children versus equal replacements, dictionary/list/definition
  aliases, and dynamic owner cache transitions in separate-process regressions.

The registry proposal does not allow transmitting unpassed public closure state,
private judge globals or RNG. Runtime implementation and acceptance remain pending.


PublicAnchorRegistry is implemented in graph_anchors.py with immutable bootstrap
records, identity-only lookup, strict key/kind/manifest checks and bounded capture.
Nineteen focused cases and source-bound Windows/Linux comparison with the independent
capture pass. This completes the registry helper, not its before-user-code startup
integration or graph commit binding. Those unchecked requirements remain pending.

PublicAnchorRegistry.private_copy now builds a disjoint, canonically equivalent
676-object private baseline, including singleton shells and native owner caches.
Three new regressions and fresh source-bound Windows/Linux diagnostics verify
aliases, private mutation isolation, frozen history and repeatable independent copies.
The codec is private to trusted bootstrap materialization, not transport admission.
Live binding and peer annotation validation remain unchecked above.
Evidence: docs/reliability-evidence/private-anchor-copy-development.md.

### Task3 implemented refinement: explicit anchor transfer

GraphArena now accepts an explicit registry and negotiates call_graph_anchors_v1.
Strict per-export anchor annotations and manifest validation bind original public
objects without interning equal replacements. Private rehearsal clones the current
closure of relevant receiver objects and supplies initial native-owner state;
commit rechecks state and identity before applying only exported objects. This
extends the frozen-bootstrap copier with the current-state phase needed after
local mutations. Independent-process alias, factory, rejection and round-trip
regressions and source-bound Windows/Linux probes pass.

The combined fixture also exposed controlled native representation depending on
base labels. The fixed native enum plus temporary base-label selection now preserve
both stored modes without rewriting the user's actual base dictionary.
See docs/reliability-evidence/anchor-transfer-development.md.

Still required: bootstrap these registries before user code in the actual worker
and judge (Task4), remaining Task3 interfaces including packed immutable operation
wrapper ownership and standalone CircuitInstruction, and full Task5 protected
counterexamples/cohorts. Do not treat direct singleton transfer as full circuit
interface admission. The overall plan and benchmark objective remain active.

### Task3 packed singleton wrappers

Stable exact-type singleton wrappers obtained through CircuitData are now explicit
operation refs in anchor-enabled sessions. Native cached values and mode remain
separate from current wrapper state, and private reconstruction retains manually
allocated singleton clones. Seven new cross-process cases and fresh Windows/Linux
factory, clone and controlled-Python round trips verify the circuit-only path.
Bootstrap/default non-anchor formats are unchanged; this is an explicit anchor
session capability. Evidence: docs/reliability-evidence/packed-singleton-wrapper-development.md.

Next: standalone CircuitInstruction and other remaining Task3 interfaces, then
before-user-code registry startup and persistent protected worker integration in
Task4. Task5 protected counterexamples, full normal/hard cohorts and whole-plan
review remain required. The benchmark goal and release blocker are unchanged.

### Execution-order refinement: protected vertical verification next

After the anchor and packed-wrapper work, begin Task4's protected call path and
six preserved identity regressions before finishing the remaining Task3 types.
This changes execution order, not scope or completion criteria: standalone
CircuitInstruction, other documented interface gaps and full Task3 admission
remain required. The purpose is to obtain evidence through the actual protected
boundary now, then use real cohort failures to prioritize the remaining codecs.
Do not keep substituting standalone codec successes for protected correctness.

Current integration points are worker.py's protocol3 value/args/kwargs lifecycle,
sandbox.py's startup handshake/call_encoded and explicit staging files, and
upstream_process.py's value-only proxy plus upstream.py's relay/source manifests.
Implement a separately identified protocol4 path with before-user-code bootstrap,
one persistent arena per side, one graph containing arguments/results/state,
strict root/sequence/session checks, and no implicit v3 fallback. Host relay must
not decode untrusted graph objects. Preserve candidate freezing, active-time and
output budgets, startup/infrastructure classification and source provenance.

Translate the six preserved native/protected cases into actual Docker regressions
first, then cover mutation-before-exception and retained earlier inputs. Initial
protected success on those fixtures is still not whole-cohort admission, and must
not be reported as complete benchmark correctness or a certified model score.

### Task4 protected graph path implemented; admission still open

A separately selected protocol4 now connects graph_worker.py and
upstream_graph_process.py through Candidate.call_graph and UpstreamJudge(protocol=4).
The explicit graph_runtime.py staging list and all graph sources are included in
configuration provenance; the existing broad source_manifest already includes new
engine modules. graph_rpc.py validates call roots and an explicit basic builtin
value-exception contract. Registry bootstrap precedes user code; per-attempt random
session IDs are recorded separately from stable configuration identity.

The six native identity cases, retained inputs, mutation-before-caught-exception,
circuit-only singleton state and malformed response cases now have actual protected
Docker tests. Fatal bridge failures remain fatal even if test code catches them.
The explicit campaign recipe upstream-graph-v4 and reference-scan --bridge-protocol 4
make protocol selection frozen and reviewable. v3 is not a graph fallback.

See docs/reliability-evidence/protected-graph-development.md. Continue with Task5's
remaining protected adversarial cases and targeted50/63/72/73/147 reference replays,
then full normal/hard calibration. Remaining Task3 interfaces and broader exception
semantics remain required; passing this vertical slice is not whole-cohort admission
or release completion. Promote the graph path as the normal default only after the
needed admission/regression evidence is reviewed; legacy defaults are not certified.

### Task3 layout and transpilation metadata

The circuit component codec now has fixed Layout slot and TranspileLayout dictionary
schemas. It preserves exposed maps, detached equal replacements, actual bit-wrapper
identities and the presence of optional latency fields. Native and protected tests
cover these relationships and malformed-state rejection. The source-guarded targeted
replay passes tasks10,16,17,18,19,20,21,25 in both suites. Tasks22/86 still require
instruction codecs, and task100 reaches the packed-operation limit.

Evidence: docs/reliability-evidence/graph-layout-development.md. Full regression
verification passed 848 tests in 364.89 seconds with no failures, errors or skips. This advances the metadata/layout requirement without
completing Task3 or removing the other admission and reproducibility requirements.

### Task3 special instruction state and native caches

Fixed LinearFunction, StatePreparation, Delay and UnitaryGate graph components
preserve actual dictionaries, raw arguments and parameter aliases separately from
native circuit caches. Native Delay/Unitary descriptors preserve fresh wrappers
and labels. Inline cached matrix storage counts against both aggregate array and
matrix budgets. Fifteen new tests include protected execution, cache divergence,
malformed matrices and memory limits. The full Docker-enabled suite passes 863
tests with zero failures, errors or skips. The source-guarded twelve-case replay
passes tasks4/5/6/22/46/86 in both suites; it is not a new aggregate score.

Evidence: docs/reliability-evidence/graph-special-instructions-development.md.
Other interfaces, the uniform resource-limit audit, complete oracle admission,
provider calibration and reproducibility remain required.

### Task3 conditional branch state and shared leaf operations

IfElseOp now preserves original Python branches separately from native branch
snapshots, including shared leaf operations and fresh compiled wrappers. Bit and
register conditions retain independent cached values. Branch trees share bounded
operation and matrix budgets. Nine new regressions include nested input mutation,
private singleton rehearsal, malformed branch data and protected execution.

The final full suite passes 872 tests in 348.98 seconds without failures, errors
or skips. The final source-guarded replay passes tasks51/72/88/121 in both suites.
Two earlier replays remain preserved: each exposed a transport defect on task72,
first operation copying and then discarded singleton caches. See
docs/reliability-evidence/graph-control-flow-development.md for all raw evidence.

The subsequent reconstruction-outcome increment separates internal owner failures
from invalid candidate payloads and removes generic ValueError/TypeError from
candidate-error handlers. Protected fault and ledger tests demonstrate score
blocking; malformed envelopes remain candidate_error. The six-case before/after
fault replay preserves identical case identities and complete source-bound chains.
See docs/reliability-evidence/graph-reconstruction-outcomes-development.md for
verification status. Actual late-owner alias support, classical expression
conditions, loops, remaining interfaces, resource configuration, oracle review
and the other release gates are still required.


### Task3 classical expression conditions

A fixed classical AST codec preserves held root identity while treating native
child getters as intrinsic values. Python IfElse conditions remain separate from
native cached expressions. Nineteen regressions cover all seven expression forms,
equal distinct roots, malformed trees, bounded recursion and protected execution.
The source-guarded task128 reference passes in both suites; raw evidence and
verification status are in docs/reliability-evidence/graph-classical-development.md.
This does not complete loop, circuit-variable/capture, duration-literal or broader
interface support. Full normal/hard admission and all other release gates remain
required; the two-case replay is not a new aggregate score.


### Task3 loop state and native snapshots

For/while loops and break/continue operations now use fixed instruction schemas.
A range component preserves retained Python identity without enumerating values;
native index sets, loop parameters and branch snapshots remain intrinsic values
with their observed fresh-wrapper behavior. Eleven new tests include compiled
loops, malformed state and actual protected parameterized loops with conditional
breaks. The task150 source-guarded reference replay passes both suites. See
docs/reliability-evidence/graph-loop-development.md for verification status.

Next refresh the complete offline normal/hard reference cohort against unchanged
source and preserve task-level changes from the historical baseline. Do not add
targeted passes to an old aggregate. External task requirements remain explicitly
in the full catalog. Remaining interfaces, uniform resource limits, oracle audit,
provider calibration and reproduction still block release certification.


### Complete post-loop reference inventory

The unchanged38db7fa source completed all286 offline cases. Each143-task suite
has113pass,28unsupported,1fail(task63),1infrastructure(task82). Exact task
identities and exclusions match3ed07d2; each suite gains33passes with no prior
pass regressions. Full raw evidence, verified chain/source and68transitions are
preserved in docs/reliability-evidence/reference-scan-38db7fa.md and its JSON
artifacts. These are calibration outcomes, not model scores or certification.

The next work must address the explicit remaining interfaces and uniform
resource policy, while task63's private RNG coupling and task82's file assumption
require declared evaluation conditions. No hidden seed transfer or implicit
semantic-recipe fallback is acceptable. The DAG allocator reproducer demonstrates
why native pickle-state reconstruction alone is not a faithful graph codec.
Full task/oracle audit, provider calibration and reproduction remain open.


### Resource configuration propagation

The graph limit record is now SDK-independent, frozen in the judge payload and
manifest, and validated by both runtime arenas. The trusted response reader uses
the same configured byte ceiling. Defaults and cumulative output accounting are
unchanged. Eight new tests and a source-bound before/after fixture verify that an
explicit 4 MiB budget works while the default 1 MiB rejection remains intact.
All 922 Docker regression tests pass; see graph-resource-contract-development.md.

Task109's 1000 calls expose cumulative full-history retransmission: the recorded
run exhausts output at call27. The next resource investigation must profile
incremental transport/reconstruction while preserving detached aliases, mutation
and validation semantics. Increasing a cap alone is insufficient. Task100's
packed-operation budget and randomized private inputs remain separate policy
issues. All prior interface, oracle, provider and reproduction gates remain open.

### Incremental transport, reconstruction still required

The opt-in `upstream-graph-delta-v1` recipe preserves graph semantics and model
requests while freezing a distinct transport identity and separate wire/state
bounds. Changed-record frames bind to the previous and resulting full state;
receivers still perform full private rehearsal and live mutation checks. Malformed
frames cannot advance the base, and uncertain outgoing/commit state closes the
session. All954 Docker regressions pass; 32 new cases cover transport, budgets,
campaign restoration and protected positive/negative controls.

The paired61-call retained-state fixture changes from snapshot infrastructure
failure after47recorded calls to delta pass under identical1MiB budgets. The
100-call local circuit profile reduces graph bytes from24,501,949 to397,729 but
increases observed time from18.34s to22.27s. Preserve this adverse timing result:
wire reduction is implemented, reconstruction performance is not solved.
Raw source-bound evidence, hashes and limitations are in
docs/reliability-evidence/graph-delta-transport-development.md.

Next address full-history capture/reconstruction costs without discarding aliases
or replacing actual live-state baselines with stale serialized history. Complete
the1000-call workload and full transport admission after that change. No default
promotion or calibrated model score is justified by this development increment.

### Validated capture reuse and live-state failure classification

Commit still recaptures the complete actual object closure and verifies every
identity, but compares against immutable validated preparation bytes instead of
encoding the baseline and validating an identical table again. The instrumented
100-call workload retains400captures and600native reconstruction calls while
record/depth validation falls from800to600passes. A single uninstrumented delta
observation falls from22.27sto19.63s with identical397729graph bytes. This is not
an asymptotic or1000-call performance solution.

Four protected controls also exposed trusted live-state races being scored as
candidate errors. These now become infrastructure errors and block scoring, even
if the private test catches them. Complete source-bound before/after evidence is
preserved in docs/reliability-evidence/graph-live-capture-development.md. Six new
regressions include equal-but-distinct supplemental children and closure after
partial live application; all960Docker tests pass. Independent read-only review
found no correctness blocker. Remaining reconstruction, concurrency guarantees,
interfaces, oracle, provider and reproduction requirements remain open.

### Task 109 oracle audit and current guide

The exact private check accepts both a fixed plus state and a parameter that only
changes global phase. The corrected trusted native probe executes all1,000calls
for four fixtures in each suite and records Bloch-vector witnesses. All8results
and call counts are verified. This exposes a coverage defect independent of the
protected transport's resource/performance issue. Preserve the two flawed
preliminary diagnostic attempts as such; they do not support normal-suite verdicts.
See docs/reliability-evidence/task109-oracle-review.md for exact evidence and limits.

A semantic revision still needs explicit domain/resource requirements and honest
finite-coverage guarantees. No oracle or runtime was changed in this audit.
The engine guide now distinguishes the implemented opt-in graph protocols from
historical v3, and keeps reference compatibility separate from oracle admission.

### Converted Gate and Instruction metadata

The pinned native converters add Gate.condition and Instruction._condition,
which the fixed graph schema previously rejected. The codec now preserves these
class-specific optional fields, absence versus null, actual dictionary identity,
and supported child aliases through mutation and deletion. Other fields and
classes remain closed. Four local controls failed before implementation; the
focused suite passes46 and the full Docker suite passes972 with zero skips.
Independent read-only review found no blocking defect.

The exact selected12-case reference comparison changes90/91/112/119/125 in both
suites fromunsupported toPASS. Task120remainsunsupported at a deeper retained
operation. Fullchains/taskselection/completions and source identities are verified;
three checkout newline-only differences are explicitly disclosed alongside the
sole semantic file change. Raw results and limitations are preserved in
docs/reliability-evidence/graph-converted-instructions-development.md. These
replays do not replace a full-cohort calibration or establish oracle admission.

### Diagonal state and completed long reference
Exact fixed diagonal/rotation classes now preserve raw state and caches; 986 Docker tests pass without skips. Task120 passes in both targeted replays. The isolated task109 hard diagnostic completed all 1000 calls with explicit expanded limits; its transcript audit passed. See docs/reliability-evidence/graph-diagonal-development.md and task109-full-delta-reference.md. Full admission, normal long-workload calibration and oracle revisions remain incomplete.

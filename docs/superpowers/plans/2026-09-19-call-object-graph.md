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

- [ ] Translate the six preserved diagnostic fixtures into protected regression tests
  with native expected outcomes: five passes and one failure, never the old outcomes.
- [ ] Initialize one arena per candidate/oracle attempt and synchronize every exported
  mutable node, not just nodes reachable from the latest arguments. Host orchestration
  forwards validated envelope bytes and never reconstructs candidate graph objects.
- [ ] Replace separately encoded value/args/kwargs fields with one graph envelope and
  exact root validation. Returned input IDs resolve to original judge objects.
- [ ] Add a retained-input test where call two mutates an object supplied in call one
  but absent from call two's arguments. Verify mutation through an old judge alias.
- [ ] Add mutate-then-raise behavior:

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
- [ ] Add a fixed inert exception allowlist and distinguish returned, raised,
  codec/runtime failure envelopes. Apply validated preceding mutations before raising
  the admitted exception in the oracle. Unknown exceptions remain unsupported.
- [ ] Preserve startup handshake, pause/resume boundaries, active-time accounting,
  byte limits, discard-result behavior and runtime/error classifications.
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
- [ ] Replay tasks50/63/72/73/147 on both pinned suites; record control-flow/RNG/oracle
  limitations separately. Never copy the private test's seeded RNG into the candidate.
- [ ] Run the full regression suite with Docker and one exclusive source-bound offline
  reference scan per suite. Compare previously passing task outcomes to the preserved
  baseline; investigate every regression before making compatibility claims.
- [ ] Record the six diagnostic native/bridge outcomes, graph/registry/source/image
  identities, malformed-payload evidence, runtime limits and unresolved capabilities.
- [ ] Update PR under the user's identity, attach it, and leave overall release
  eligibility false until all unrelated benchmark requirements are verified.

## Self-review and execution state

The ten spec invariants map to Tasks1–5: identity/topology/validation (1), storage
and nested ownership (2–3), persistent calls/exceptions/privacy (4), and adversarial
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

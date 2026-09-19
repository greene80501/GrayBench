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
`populate(object, state, resolve)` and `apply(object, state, resolve)`.
`ref(object)` returns a scalar or exact `{ref: id}` record; `resolve(id)` returns
only an already validated/allocated graph object. `shape_index` contains validated
node kinds and structural dimensions, not arbitrary object access. These interfaces
are implemented in Task 1 and consumed unchanged in Tasks 2 and 3.

Run all commands below from `work/GrayBench/engine`; use `uv run --extra qiskit
--extra dataset pytest ...`. Format before source-bound protected replays.

### Task 1: Container graph, arenas and transactional validation

Files: create `graph_wire.py`, `graph_types.py`, `tests/test_graph_wire.py`.
Produces the arena/codec interfaces above, with list/tuple/dict/PropertySet support.
Do not route production candidate calls through the new arena yet.

- [ ] Write the shared-reference regression and observe failure on the old codec:

```python
def test_shared_positional_keyword_object():
    shared = []
    roots = {"args": (shared,), "kwargs": {"b": shared}}
    sender = GraphArena(side="judge", session="test", limits=GraphLimits())
    receiver = GraphArena(side="candidate", session="test", limits=GraphLimits())
    actual = receiver.commit(receiver.prepare(sender.snapshot(roots, sequence=1), sequence=1))
    assert actual["args"][0] is actual["kwargs"]["b"]
```

- [ ] Implement traversal with strong-reference ID maps, exact schemas and fixed
  ownership prefixes. Allocate mutable shells first, build tuple dependencies,
  then populate mutable containers. Charge nodes/edges/bytes across the entire arena.
- [ ] Test a self-referential list, mutual list/dict cycle, tuple containing a list
  pointing back to that tuple, ordered mappings and PropertySet missing-key behavior.
- [ ] Test equal-valued distinct objects remain distinct, replacements get new IDs,
  and an existing immutable tuple ID cannot acquire a different state.
- [ ] Add a failed-preparation test: existing list `[1]`, malformed later reference;
  `prepare` raises WireError and the list remains `[1]`. Repeat with duplicate IDs,
  dangling references, unknown kinds, foreign sessions, stale sequence, boolean IDs,
  invalid ownership and structural/byte-limit exhaustion.
- [ ] Add a second snapshot retaining an old detached child; mutations of that child
  must update its original receiver object even when it is no longer in current roots.
- [ ] Run focused tests and lint, request bounded review, resolve findings, commit.

### Task 2: Numeric storage and scientific/primitive object ownership

Files: create `graph_numeric.py`, `tests/test_graph_numeric.py`; modify `graph_types.py`.
Consumes Task 1's fixed NodeCodec contract and arena references. Produces graph-aware
numeric/scientific/primitive handlers with explicit rejection of unsupported forms.

- [ ] Write native/graph shared-storage tests before handlers:

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
- [ ] Represent owning numeric buffers and array views with validated dtype, offset,
  shape, strides and writeability. Validate min/max byte addresses for positive,
  negative and zero strides before allocation. Never use object/structured dtypes.
- [ ] Test disjoint equal arrays stay disjoint, overlapping slices, transposes,
  negative strides, read-only views, endian preservation and nonfinite numeric bytes.
- [ ] Map Statevector/DensityMatrix/Operator/Choi, ScalarOp/SparsePauliOp,
  Clifford/StabilizerState/CNOTDihedral and BitArray/DataBin/PrimitiveResult/
  PubResult/SamplerPubResult to explicit component references. Reuse existing numeric
  field validation, not opaque deep copies. Every existing tree-supported type gets
  either a graph handler or an explicit unsupported capability entry.
- [ ] Test two wrapper objects sharing one numeric array, repeated DataBin fields,
  metadata shared with a separate argument, and a symbolic coefficient shared by
  multiple operators. Test inconsistent dimensions/state and reserved DataBin fields.
- [ ] Run focused tests, review memory/ownership validation, commit.

### Task 3: Qiskit circuit and instruction component graphs

Files: create `graph_circuit.py`, `tests/test_graph_circuit.py`; modify `graph_types.py`.
Consumes Tasks 1/2. Produces graph-aware handlers for current circuit/instruction
families; new control-flow support remains a separate codec requirement.

- [ ] Record native pinned-SDK identity behavior for registers/bits, circuit data
  wrappers, instruction copies, parameters, cached definitions and metadata. Turn
  each supported relation into a graph round-trip or update assertion.
- [ ] Write the held-metadata/returned-root regression:

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

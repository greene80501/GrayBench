# Persistent call object graph design

Status: implementation design under the user's approved end-to-end overhaul.
A standalone container/numeric graph is under implementation; production graph
protocol integration and admission remain unfinished. Existing PR and
source-bound evidence remain development-only. This is an architectural change,
not a special-case patch for task147. Execution continues under the standing
implementation authorization; this document does not claim separate user review.

## Goal and invariants

Preserve the observable identity and mutation behavior of admitted Python/Qiskit
objects when a protected test invokes a candidate in another container. Keep
private tests, references, judge globals and RNG state out of that container.

1. Repeated references within args, kwargs and their nested objects stay repeated.
2. A result referring to an input resolves to the existing judge object.
3. Mutations update the existing object rather than replacing every equal value.
4. Replacing an object by a new equal-valued object is distinguishable from mutation.
5. Identity persists across calls, including previously returned objects reused as inputs.
6. Mutations to retained earlier inputs are observable after later calls, even when
   those inputs are not among the later call's explicit arguments.
7. Cycles terminate under node/edge/byte limits; malformed references cannot target
   private judge objects or change an existing handle's type.
8. Validation completes before an update is applied. Failed validation changes no
   judge object. An unexpected apply-time failure terminates the attempt; evaluation
   cannot continue with a partially changed graph.
9. Identity-sensitive state inside SDK objects is either represented explicitly or
   causes a declared unsupported result. Reusing the old codec as an opaque leaf
   is not permission to silently duplicate internal references or shared storage.
10. Candidate exceptions never become a verdict. Admitted exception types and
    before-raise mutations must retain native test-observable behavior.

## Alternatives and decision

Value snapshots plus per-type copying do not preserve aliases, equal-valued
replacements or cross-call identity; the six probes disprove this approach.
Remote Python object proxies preserve handles but fail concrete Qiskit type checks
and greatly expand the trusted callable interface. They are not selected.

Use a versioned, bounded, data-only object graph and session arenas on both sides.
Fixed type codecs define state fields and in-place update behavior. The graph never
names arbitrary constructors, imports, attributes or executable reconstruction code.

## Wire model

Call protocol v4 carries one graph snapshot with named roots `args` and `kwargs`.
Response roots include `value`, `args_after`, `kwargs_after` and the previously
exported mutable nodes whose state the candidate can still mutate. They share one
reference namespace. No separate serialization of the three result components.

A snapshot has exact keys `format`, `session`, `sequence`, `roots`, `nodes`.
`format` is `call_graph_v1`. Object IDs have fixed ownership prefixes `j:` and `c:`
plus bounded nonnegative integers. Judge-created IDs are assigned only to objects
actually supplied to the candidate; candidate-created IDs are assigned only to
objects returned or reachable from exported state. Ref records contain only `ref`.
Scalar values retain the existing finite/typed scalar rules; their identity is not
an admitted contract. Node records contain only `id`, a fixed `kind`, and that
kind's validated `state`. Scalars must never be interpreted as object references.

A SessionArena pins represented objects to avoid Python id reuse and retains
handle-to-object and object-id-to-handle maps. Persisted handles use the same objects
on later calls. Arena and transport resources stay bounded for the whole attempt,
not merely per message: at most 100,000 nodes, 100,000 edges per snapshot, existing
message byte limits, existing depth limits for typed nested state and existing
array/matrix allocation limits. Exceeding a limit is unsupported, never a wrong
answer or a fallback to the value-only bridge. Weak-reference/finalizer/garbage-collection observations and primitive scalar
identity are outside this admitted contract; arbitrary Python execution equivalence
is not claimed. Strong references are released when
the candidate/test attempt closes. Automatic deletion of objects that might still
be referenced by either side is not permitted.

The full first snapshot creates admitted objects; later snapshots reconcile their
states. Objects absent from the current arguments may remain live through candidate
globals or judge aliases. All previously exported mutable nodes, including detached children, are synchronized, while
unpassed private judge objects must never be enumerated or serialized.

## Type capabilities and state ownership

Start with list, tuple, dict and PropertySet graph nodes. List/dict shells support
cycles. Tuple dependencies are built after mutable shells; an impossible pure
immutable construction cycle is rejected. Ordered dictionary entries and key
validation retain current codec rules. Shared tuple identity is preserved, although
primitive scalar identity is outside the admitted contract.

QuantumCircuit support must model circuit/register/bit membership, mutable
instructions and definitions, parameters, metadata and layout as owned/referenced
state. A root object must not be replaced just to apply a new circuit snapshot.
External references to metadata or contained instructions are part of the graph.
Record and test which Qiskit getters return stable objects versus value wrappers
in the pinned 2.4.2 runtime; wrapper identity cannot be invented by serialization.

Numeric arrays require buffer/offset/shape/stride/read-only information when storage
is shared. Rebuilding every view as an independent contiguous array is forbidden.
Operator/Statevector/DensityMatrix/Choi, ScalarOp/SparsePauliOp, Clifford/
StabilizerState/CNOTDihedral and primitive result/DataBin/BitArray types expose
mutable numeric/container state that must use graph references. Instruction types
already supported by the tree codec also need graph-aware base/cache/parameter
relationships. Unsupported forms stop explicitly; no unsupported class may silently
fall back to value-only snapshots in a graph campaign.

Each admitted type has fixed `allocate`, `validate_state`, `populate` and `apply`
functions. This is a closed registry, not user-supplied method names. Constructors
must not normalize invalid submitted physical states. Validation includes counts,
shape consistency, control flags and alias/storage constraints before mutation.

## Call and exception lifecycle

The trusted oracle arena exports only explicit arguments and known exported roots.
The host forwards bounded graph bytes without reconstructing candidate objects.
The candidate arena resolves them to persistent local objects, runs the function,
and returns a graph of result and post-call state, including retained inputs.
The trusted oracle validates the entire graph, allocates new nodes privately,
then applies the update and resolves the return root to an existing or new object.

A normal Python exception can follow a mutation. A v4 response distinguishes a
returned value, an admitted raised exception, and a transport/runtime failure.
Only a fixed allowlist of inert exception types can be reconstructed; unknown
classes remain unsupported. The original message is bounded data, not executable
code. The oracle can catch the admitted exception and observe preceding mutations.
Startup errors, timeouts, codec failures and resource exhaustion retain separate
infrastructure/interface classifications. Private test stack frames never cross
into the candidate.

## Migration, audit and acceptance

The call protocol, graph registry digest, source/image, limits and identity scope
are frozen in judge/campaign manifests. Old evidence remains tied to protocol v3;
there is no automatic rejudgment or reinterpretation. A new graph campaign cannot
resume with the old worker or silently downgrade unsupported graph nodes.

Acceptance requires all six synthetic identity probes to match native execution,
with the incorrect identity function failing. Also require cycle/storage/update
security probes, in-place Qiskit references and held nested aliases, and mutation
before an admitted exception. Re-run actual tasks50/63/72/73/147 and report remaining
independent boundaries rather than forcing references to pass. Task63's private
RNG seed is not part of the explicit call graph and must not be leaked.

Protected tests must verify candidate mounts still exclude tests, keys, Docker
socket and arbitrary reconstruction code; typed graph data does not authorize
host execution. Complete source-bound reference replay and previously passing
regression comparisons are required before claiming a broader admitted interface.
Graph fidelity alone does not certify the entire benchmark or complete the goal.

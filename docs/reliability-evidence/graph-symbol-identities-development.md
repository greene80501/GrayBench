# Symbol identities and parameter-vector ownership

The standalone graph now admits exact Qiskit Parameter, ParameterVector and
ParameterVectorElement objects, plus UUID objects needed by vector slots.
Production calls still use the old bridge: this development increment does not
resolve the [production identity defects](alias-boundary.md) or admit model scores.

Each Python object has its own arena ID. Equal UUIDs do not merge distinct
parameters, vector elements or vectors. Vector parameter lists and root UUID
objects are referenced directly, preserving separately supplied aliases.
Shrinking a vector retains its list and detached elements; regrowing creates
new elements that can compare equal to old elements without being identical.
An explicitly constructed element may have an index beyond the current vector
length and an arbitrary UUID. The graph preserves those native SDK forms.

Parameter UUID getters produce temporary Python wrappers in the pinned SDK.
Their UUID values are intrinsic descriptors, not invented persistent child
references. Element.vector, vector.params and vector._root_uuid are actual
persistent references and are graph edges. Reconstruction uses only fixed local
classes, bounded names, canonical UUIDs and integer indices. No pickle, expression
strings, payload-selected constructors or UUID-based object interning is used.

The vector list and root UUID can be replaced while old exported objects remain
retained. Exported vector renaming is explicitly unsupported, as are elements
whose stored names disagree with the current vector name. Limits include 256
characters per symbolic name, 4096 vector-list entries and indices 0 through 4095,
in addition to the arena's total node, edge, depth and message limits.
Names must encode as UTF-8. UUID safety flags retain their exact fixed enum value.

## Evidence

The initial twelve tests failed because these graph types were unsupported, then
passed. Additional adversarial and boundary cases bring the new file to 23 tests.
A new-node malformed Unicode-name test independently exposed an escaping
UnicodeEncodeError; validation now rejects it as WireError before reconstruction.
Together, all six graph test files passed 158 tests.
The full Docker-enabled suite passed **594 tests** in 189.70 seconds, with no
failures, errors or skips. Local JUnit artifact:
outputs/GrayBench-v4-symbol-identities-full-tests.xml. Ruff lint and formatting passed.

The trusted standalone probe passed 16 checks in pinned image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd,
with Python 3.12.14 and Qiskit 2.4.2. Nine dependency modules and the fixture
were mounted read-only, with no network, user 65534, 512 MiB memory, one CPU,
64 PIDs and a 16 MiB temporary filesystem. This is not a protected v4
candidate/oracle replay. All reported source hashes were checked against the
actual mounted bytes, which can use Windows CRLF rather than Git-normalized LF.

[Raw probe](GrayBench-v4-symbol-identities-linux-probe.json) SHA-256:
cee0ce1a16344b2b86b51a769a6977d2909f45b99ef8d0b9d86da7a14dd0f81c.

## Remaining work

ParameterExpression replay and object-reference arrays remain unfinished.
A native probe confirms that constant expressions currently decode to Python
numbers in the old tree decoder; reusing it unchanged would lose type fidelity.
Expression getters also create temporary parameter wrappers. Those must not
be confused with persistent object edges. Symbolic SparsePauliOp coefficients,
array geometry updates, circuit ownership, v4 RPC integration and full protected
admission remain outstanding. No model generations ran for this increment.

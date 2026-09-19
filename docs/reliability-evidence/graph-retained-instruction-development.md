# Retained Python instructions and native caches

Exact plain Gate/Instruction and the basic mutable standard instruction classes
now have component graphs. A fixed local class table selects types; the payload
cannot import classes or select constructors. Their actual instance dictionaries,
parameter lists and raw cached definitions are graph references. This preserves
shared lists, equal-valued replacements, detached aliases and recursive definitions
without reading the lazy definition property or synthesizing a decomposition.

A native probe and regression showed that CircuitInstruction retains a Python
operation while separately caching its original name, parameters and label. Two
circuits can retain the same gate yet have different cached parameters. Rebuilding
from the current gate alone changes this state. The graph now records both layers.
For fixed exact classes, owner finalization temporarily attaches a bounded dictionary
of the recorded cache fields, constructs the native instruction retaining that same
operation, and restores its actual dictionary in a finally block. Full private
rehearsal and canonical re-encoding precede live commit. This assumes the existing
single-threaded/frozen candidate boundary; it is not a concurrent object updater.

The cached parameter list itself is a fresh native wrapper. Symbolic entries use
intrinsic bounded replay with actual ParameterVector references; Python array
entries retain actual graph references. The gate's own parameter list stays a
separate ordinary graph component. Scalar-aware canonical owner references now
handle cached literals as well as object references.

The pinned [Qiskit 2.4.2 Rust operation source](https://github.com/Qiskit/qiskit/blob/2.4.2/crates/circuit/src/operations.rs#L2943) confirms that native Python operations separately store qubit/clbit/parameter counts and a name alongside the Python object. Its [instruction construction source](https://github.com/Qiskit/qiskit/blob/2.4.2/crates/circuit/src/circuit_instruction.rs#L867) reads these values when constructing the native record. These sources support the observed distinction; they do not establish complete transport fidelity.

## Cached arity

Changing a retained operation's qubit or classical-bit count leaves the original
native counts cached. Naive reconstruction silently changes them. An initial
nonlocal-count guard rejected the one-to-two-qubit discrepancy but could not
distinguish two from three qubits. Three subsequent RED tests required exact
preservation of both cached and current qubit/clbit counts.

[DAGOpNode.from_instruction(deepcopy=False)](https://github.com/Qiskit/qiskit/blob/2.4.2/crates/circuit/src/dag_node.rs#L236), a fixed pinned-SDK factory, exposes
the native arities without reconstructing or copying the retained operation.
The final implementation records those exact counts and installs them with the
other temporary cache fields during native reconstruction. Canonical re-encoding
checks both arities. No circuit-to-DAG conversion or generated circuit name is
needed. Both sides retain the original Python operation and its actual dictionary.

Controlled classes, singleton identity, layouts, variables and symbolic global
phase remain unfinished. Other native cache forms still require their own audit;
these cases do not establish general instruction compatibility.

## Verification

Nine initial tests failed at missing codecs; all twenty-one final instruction tests
pass. Cases include exact dictionary/list identity, raw definition sharing without
synthesis, recursive definitions, two distinct native caches sharing one gate,
labels, mutable standard operations, array storage, symbolic vectors, classical
operands, detached parameter lists, malformed refs/class selectors and rejection
of unsupported subclasses, and exact preservation of stale native arities.

The final full Docker-enabled suite passed **730 tests** in 191.41 seconds,
with no failures, errors or skips. JUnit artifact:
outputs/GrayBench-v4-retained-native-arity-full-tests.xml. The focused circuit,
instruction and owner group passed56 tests. Ruff lint,113-file formatting and
secret-value diff checks passed. Earlier727/728 full reports are retained as
intermediate evidence preceding the final arity implementation.

The trusted standalone pinned Linux probe passed 25 checks. Its nineteen modules
and fixture were mounted readonly with no network, uid 65534, 512 MiB memory,
one CPU, 64 PIDs and a 16 MiB tmpfs. Source/probe hashes were checked against
mounted bytes. [Final raw result](GrayBench-v4-retained-native-arity-linux-probe.json)
SHA-256: 5f96e680ee9eb57b2a3bd117939653d6394b023caa76a9672cc3e53e649917de.

The earlier 24-check result is preserved separately as
GrayBench-v4-retained-instruction-linux-probe.json, SHA-256
3ce8a10f4f23bc9b9540553aa276c4473f1040931c775f3b1689247a6055fc6d.
It predates exact cached-arity preservation.

Production still uses v3. The six preserved identity verdict defects remain a
release blocker until protected v4 integration and adversarial acceptance tests.
No model generations or new full reference cohort were run in this increment.

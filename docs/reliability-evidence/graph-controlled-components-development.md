# Controlled components and retained native representation

The standalone instruction graph now has fixed controlled component schemas.
The exact ControlledGate, MCXGate and matching standard controlled classes use
raw base_gate, _num_ctrl_qubits, _ctrl_state and _open_ctrl fields in addition to
the existing actual dictionary/parameter/definition references. Base components
must themselves have admitted codecs. Shared singleton bases remain unfinished;
this change does not admit all controlled gates merely by recognizing their class.

Public controlled params delegates through the actual base graph. Raw _params is
preserved independently, including its list identity. Shared bases, shared raw
definitions, nested bases and detached replaced bases retain their own handles.
Cycles and excessive nesting in base delegation are rejected before property
recursion or native reconstruction. Raw definitions are never lazily synthesized.

Retained instruction records now explicitly include native_standard. The current
Python operation's control state is not used to infer the existing native role.
Canonical owner verification compares that selector as well as names, parameters,
labels, operands and cached arities.

During private rehearsal and live commit, fixed reconstruction temporarily provides
cached parameter values through the base chain, then restores every original
instance dictionary in reverse order in a finally block. For native standard
controlled gates, the closed state is taken from the fixed SDK template of the
matching class. For native Python standard-controlled objects, the cached decorated
name supplies its bounded open-control suffix. Plain ControlledGate uses its full
cached name directly. This never changes the declared current Python control state
or replaces its public parameter list with the cached list.

## Verification

Six initial positive/malformed-state cases failed at the missing class codec; the
base-cycle rejection already passed. After component support, both native-role
transitions failed canonical reconstruction. Recording the role and delegated
cache reconstruction resolved them; the closed reconstruction additionally required
the template's closed ctrl_state, not only an _open_ctrl flag.

Thirteen controlled regressions pass. They cover actual dictionaries, base/public
and raw parameter lists, shared/nested/replaced bases, shared raw definitions,
control changes before initial transfer and on already-transferred roots, generic
open names, cycles, malformed flags and forged representation selectors. Direct
Operator matrix comparisons agree for both standard/Python role transitions.
The preexisting circuit/instruction/owner group also passed with the initial seven
controlled cases (63 combined). The final focused controlled run includes all13.

The full Docker-enabled suite passed **743 tests** in193.24 seconds, with no
failures, errors or skips. JUnit: outputs/GrayBench-v4-controlled-components-full-tests.xml.
Ruff lint,115-file formatting and secret-value diff checks passed. The additional
matrix assertions were verified in the final13-case focused run.

The pinned Linux standalone probe passes26 checks, including both control-state
transitions with retained native representation and no synthesized definitions.
Nineteen source modules and the fixture were mounted readonly with no network,
uid65534,512MiB memory,one CPU,64PIDs and16MiB tmpfs, in image
sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd.
Reported source/probe hashes were verified against actual mounted bytes.
[Raw result](GrayBench-v4-controlled-components-linux-probe.json), SHA-256:
0c2d6b17970a8bbbb1f7a70d8add396ed38b8a1f993f95c3b398dbb5292220ec.

This remains standalone development work. Singleton identities, remaining native
instruction forms and circuit components, protected v4 integration, adversarial
acceptance and full cohort admission remain incomplete. No model generation or
new aggregate benchmark score is produced by these checks.

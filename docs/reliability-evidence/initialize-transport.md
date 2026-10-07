# Exact Initialize graph transport

The previous [Task66 W-state bundle](artifacts/task66-symmetric-w-2026-10-07/README.md)
retained two correct initialization controls as unsupported. This change adds
the exact pinned Qiskit Initialize class to the existing data-only graph codec.
The [new bundle](artifacts/task66-initialize-transport-2026-10-07/README.md) transfers
all 84 controls: 32 pass and 52 fail, matching their direct judgments. The original
prompts, revised public prompts, checker, control completions and resource profile
are unchanged. Earlier evidence retains its original source binding.

## Representation and cache fidelity

The pinned [Initialize implementation](https://raw.githubusercontent.com/Qiskit/qiskit/2.4.2/qiskit/circuit/library/data_preparation/initializer.py)
retains a StatePreparation object and delegates its public parameters to that
object. The existing [StatePreparation representation](https://raw.githubusercontent.com/Qiskit/qiskit/2.4.2/qiskit/circuit/library/data_preparation/state_preparation.py)
retains original input data, flags and definition caches. Initialize now transmits
its raw dictionary and preparation reference through that representation. The
decoder requires the linked exact registered StatePreparation role. It does not
call Initialize or StatePreparation constructors, force synthesis, normalize data,
decompose the answer or substitute a copied value. Unsupported additional fields
remain explicit.

Qiskit's native circuit entries cache parameters when an operation is inserted.
Those values can differ from the retained Python operation's current parameters.
Reconstruction temporarily supplies each entry's cached parameters through both
raw dictionaries, creates the native entry with the same retained operation, and
restores both original dictionaries in a finally block. Current aliases, detached
parameter lists, shared preparations, labels, names and existing lazy or populated
definition caches remain distinct from insertion-time caches.

## Verification boundaries

The focused host tests cover list, array, Statevector, label, integer and normalized
inputs; independent density targets; two wrappers sharing one preparation;
different native caches; reverse updates and detached aliases; both lazy and fully
synthesized definitions; production delta calls in both ownership directions;
existing storage limits; invalid linked roles; malformed updates; and restoration
after a native reconstruction exception. Red tests exposed the missing class,
incorrect native cache reconstruction and a malformed-state type error before
the corresponding changes passed.

An additional read-only AI review found no actionable defects and independently
probed shared preparations, reverse replacement and populated definition caches.
This is finite host evidence. Both arena sides use trusted authored objects on
one host; public anchors are captured in the same process. It does not authenticate
candidate-side encoding or prove equivalent behavior in independent processes.

The immutable-image integration test and full isolated W-state roster remain
skipped while Docker is unavailable. SDK evolution, runtime resources, adversarial
encoder integrity and independent human task/oracle admission remain unqualified.
No model, API, sampler or native-build execution was used. The benchmark and this
development condition remain release-ineligible.

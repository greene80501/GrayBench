# Protected task-2 Bell amplitudes development contract

Status: design for a development-only revision. The dual-track QHE design
authorizes explicit value-based revisions but does not admit a task or publish a
score.

## Problem and choice

Both pinned task-2 tests call `candidate().equiv(solution)`. A forged object or
subclass can return `True` without Phi+ amplitudes, as reproduced in
[`task2-statevector-oracle-review.md`](../../reliability-evidence/task2-statevector-oracle-review.md).
Candidate-side native-object serialization is also mutable by candidate code.
The protected track will instead ask for a declared numeric value and check it
in the host. This changes the public requirement and receives a distinct task
and oracle identity. The original pinned task and native result remain intact.

## Public and private contract

The normal revision is a Python function completion; the hard revision asks for
a standalone function. Both require `bell_amplitudes()` with no arguments to
return four `[real, imaginary]` pairs in Qiskit's little-endian statevector
order. Each finite component is bounded to `[-1,1]`. The intended state is
Phi+ = `( |00> + |11> ) / sqrt(2)`, with arbitrary global phase. The public
contract declares zero relative tolerance and `1e-10` absolute tolerance on
aligned amplitudes and norm. Qiskit may be used, but the result is judged only
as a value; no `Statevector` identity, circuit construction, or algorithm is
attested.

The trusted host independently checks finite shape, norm, nonzero overlap,
global-phase alignment, and each amplitude against Phi+. One frozen no-input
case is sufficient to invoke this contract; distinct candidate implementations
and wrong mutants test the oracle itself. Positive controls include direct
mathematics, a Qiskit circuit-derived state, and a global-phase variant.
Negative controls include Phi-minus, product states, a fixed wrong basis
state, unnormalized and malformed values, and forged verdict text. Candidate
serialization cannot set the host verdict.

## Integration and limits

A small reviewed-revision registry maps only pinned task IDs 2 and 20 to
constructors. Protected cohort and setup validation reconstruct each revision
from pinned source bytes. The CLI may schedule either or both within one
normal or hard suite, with all unscheduled tasks explicitly excluded. Manifests
bind the revision source, public contract, cases, oracle, runtime, and engine
source. Every result remains `development_only` and `publication_eligible:
false`. No claim follows about unchanged QHE task 2, secret holdouts, or full
151-task coverage. Independent Qiskit review and task admission remain open.

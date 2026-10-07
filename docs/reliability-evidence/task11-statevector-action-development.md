# Source-bound statevector action for Task 11

Both pinned tests call `get_statevector` on one two-qubit U-plus-CX circuit.
A fixed Statevector for that example passes while ignoring the argument. On a
two-qubit X-on-qubit-0 circuit, the expected basis state has index one and the
fixed answer has no amplitude there. The [host diagnostic](artifacts/task11-statevector-action-2026-10-07/report.json)
retains the original outcomes and this independently specified counterexample.
It does not imply that any model used the shortcut.

`qhe11-statevector-action-graph-v1` is a separate, explicitly selected development
condition. Original tasks, tests and results remain unchanged. Its public domain
is numeric unitary circuits on one to five qubits, without classical bits or
unbound parameters. It asks for the original circuit's action on the all-zero
state in little-endian computational-basis order, with matching qubit subsystem
dimensions. Input mutation is permitted, but may not change the action reported.
A unit-modulus global phase is allowed; after alignment, amplitudes have absolute
tolerance `1e-10` and zero relative tolerance.

Normal retains imports and a typed function prefix; hard retains a standalone
function instruction. Both receive the same revised requirements, without
private cases, expected amplitudes or authored solutions. Original or exact
revised records are accepted only after reconstructing both exact source
identities. Changed references, tests, prompts, entries and formats are rejected.
The revision is frozen before generation, with separate task/judge/comparison
identities. It cannot be pooled with an upstream score.

The checker constructs 43 actions from literal X/H/S/U/RX matrices, little-endian
tensor embeddings and indexed CX permutations. Cases cover widths one through
five, identity and spectator wires, both CX directions, relative complex phases,
a bound parameter, register insertion order and a supplied gate definition on
reversed wires. Expectations are frozen before dispatch. The maximum difference
from SDK simulation is `4.577566798522237e-16` in the saved environment. This
finite corpus does not establish correctness for every circuit in the domain.

The [roster](task11_controls.py) has 16 authored implementations per format:
five expected passes and eleven expected failures, totaling 32 trials. Correct
alternatives include operator-column extraction, a separate basis-index
simulator, an equivalent global phase and permitted mutation. Wrong controls
ignore inputs, reverse wires, conjugate phases, invert action, report modified
inputs, scale magnitude or return wrong widths/types, nonfinite values and huge
finite values. The checker bounds components before phase arithmetic. Both
manifests and the entire roster are reserved in a new append-only log before
isolated execution begins.

This condition freezes graph protocol 4, delta transport and individual calls,
with depth 128 and a default 16 MiB state/wire/output allowance. Existing array,
matrix, node and edge limits apply. A different selected byte allowance changes
the judge identity and is rejected by a default frozen plan. Local retained-graph
tests exercise all 43 calls for every correct alternative in both formats,
including mutation and array-backed views. They verify returned semantics, not
native identity, internal methods, container isolation or provider behavior.

The manifest remains runtime-unqualified and release-ineligible. Select
`GRAYBENCH_STATEVECTOR_TEST_IMAGE` only for a separately qualified immutable image
when verifying the complete isolated roster. Docker recovery, resource
calibration, adversarial worker qualification and independent admission remain
required. Authored alternatives are not human reviewer attestations. The current
registry flags both task-11 cards; historical registries and evidence stay frozen.

From `engine/`, freeze a new plan:

```sh
uv run graybench campaign-plan model.json CACHE NEW_SETUP.json --name state-action-development --image sha256:QUALIFIED_IMAGE_DIGEST --evaluation-recipe qhe11-statevector-action-graph-v1 --task normal/qiskitHumanEval/11 --task hard/qiskitHumanEval/11
```

After runtime qualification, reserve and run isolated controls:

```sh
uv run python ../docs/reliability-evidence/task11_controls.py --cache CACHE --image sha256:QUALIFIED_IMAGE_DIGEST --output NEW_CONTROL_LOG.jsonl
```

The [Qiskit 2.4 Statevector documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.quantum_info.Statevector)
defines circuit-to-state simulation and state dimensions. The
[RXGate documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.4/qiskit.circuit.library.RXGate)
defines the local rotation matrix used in calibration. These inform the contract,
but do not establish this finite oracle's adequacy.

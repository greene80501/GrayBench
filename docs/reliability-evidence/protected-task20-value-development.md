# Protected task-20 value revision: development evidence

This is a new `graybench-protected-semantic-v1` task descended from the pinned
normal and hard `qiskitHumanEval/20` records. It is **not** the unchanged
Qiskit HumanEval task and is not admitted for a published score. The original
prompt asks for a `QuantumCircuit` transpiled through a pass manager for
`FakePerth` at initial layout `[2,4,6]`. The original test checks only circuit
width and the initial layout, allowing an empty circuit to pass. The revised
public prompt instead asks for a seven-qubit GHZ+ statevector as 128 complex
amplitude pairs for a supplied three-wire layout. It explicitly permits
Qiskit but scores only the returned numeric value. No pass-manager use,
`QuantumCircuit` identity, or native side effect is attested.

| Suite | Pinned source digest | Revised public digest | Revised value contract digest |
| --- | --- | --- | --- |
| normal | `50c85aa2a066db0be117730d7b916d7522ccb282002b802ee1a9112c405571ad` | `c8ac5208cf51d30977a032355c3fa95807239248b453e6192ad8a5a6834a85a0` | `cd81bb0840e4e9e30c93bf30c812bfcbbded99de296b7fefcc8a529d76da7080` |
| hard | `a39d624d99ec39b312f116204d9c9d4af41ca3f89ab07005bbea2952d456c217` | `0fa244d920dbbb2069b98b724c9363a61b8551273893908b5917717628a32ad5` | `4e9302594084b72b480cd56c38013b0f96bec5f92f7d4789eec81a455507b550` |

This document describes the original three-case v1 oracle. It is retained as
historical development evidence. New task-20 protected plans use the separately
identified [all-layouts v2 oracle](task20-all-layouts.md). The v1 private case
set uses layouts `[2,4,6]`, `[0,1,2]`, and `[1,3,5]`.
The trusted host-side oracle checks unit norm and fidelity one against GHZ+
on the selected physical wires, up to global phase, in Qiskit's little-endian
statevector order. Each real and imaginary amplitude is constrained to
`[-1,1]`, the physical range for a normalized state. The candidate container
receives each input layout but no expected amplitudes or oracle code. It returns
a bounded JSON value; the host
validates its declared shape before the oracle runs. A candidate can compute
or fabricate the correct numeric value. That is a correct answer to this
revised value task, never proof of how it was computed.

Local pinned-image controls on 2026-09-27 used Python 3.12 and image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`.
The direct mathematical implementation, a Qiskit `Statevector` implementation,
and a global-phase variant passed. Empty and wrong-length arrays were candidate
format errors; the zero state, fixed-layout answer, and wrong relative phase
failed. Forged pass text was rejected as malformed output. The hard-suite
revised prompt also passed a direct implementation. Focused verification:
`pytest tests/test_protected_semantic_judge.py tests/test_protected_value_runner.py -q`
with the pinned cache/image set: 16 passed after an adversarial review. The
additional controls reject finite but nonphysical `1e308` amplitudes, classify
candidate-triggered nonzero exits separately from Docker launch failures, and
block an invalid judge-owned call as infrastructure rather than candidate error.
Ruff passed on the new files.

This automated evidence does not replace independent Qiskit review. The task
card remains pending, the release flag is false, and no protected model score
or 151-task claim follows from these controls. Before admission, reviewers
must decide whether this revised, value-based requirement belongs in a
released benchmark and independently validate the domain, oracle, and controls.
The three development inputs are checked into this repository and are not an
unseen holdout; a released revision needs a separately frozen, reviewed case
set and a disclosure of possible training exposure.

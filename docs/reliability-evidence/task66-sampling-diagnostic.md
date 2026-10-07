# Task66: count-test variability and phase blindness

The pinned normal and hard tasks ask for a circuit preparing and measuring a W
state. Their exact source digests and test hashes are preserved in the
[predeclared plan](artifacts/task66-sampling-diagnostic-2026-10-07/plan.json).
Both private tests require three qubits, computational-basis counts with keys
`001`, `010`, `100`, each count between 300 and 400 inclusive, and total 1024.
The prompts do not state the width, shot total, count thresholds or classical
register name `meas`. The normal prefix supplies `QuantumCircuit`, `arccos` and
`sqrt`; hard intentionally omits these imports.

## Exact conditional false-rejection probability

For the symmetric three-qubit state

$$|W\rangle=(|001\rangle+|010\rangle+|100\rangle)/\sqrt{3},$$

ideal independent shots have three equally likely outcomes. The probability of
the private count test accepting is exactly

$$P_{\rm accept}=3^{-1024}\!
\sum_{\substack{a+b+c=1024\\300\leq a,b,c\leq400}}
\frac{1024!}{a!b!c!}.$$

Two integer-arithmetic derivations agree: a binomial coefficient sum over valid
pairs and a factorial multinomial sum over all bounded triples. Tests independently
enumerate every ordered three-label outcome sequence for shot counts zero through
seven over all inclusive bounds. The report saves reduced exact integer fractions.

The resulting ideal rejection probability is **0.007756595364539097**, approximately
**0.77566% per run**. This is conditional mathematical calibration, not an observed
Aer/Runtime sampler failure rate. It assumes independence and exactly one-third
probabilities and excludes imports, transpilation, runtime defaults and other
failure paths. Under the additional hypothetical independence of 20 replays,
the approximate chance of at least one rejection is 14.42155%; those replays were
not executed. A finite repeat screen does not eliminate this source of variability.

## What the counts cannot establish

Computational-basis probabilities depend on squared amplitude magnitudes, so
relative phase can change the state without changing these probabilities. The
pinned [Qiskit 2.4.2 Statevector source](https://raw.githubusercontent.com/Qiskit/qiskit/2.4.2/qiskit/quantum_info/states/statevector.py)
defines this probability calculation. The diagnostic checks nine trusted authored
circuits against independently specified probabilities and symmetric-W fidelities:

| Construction | Symmetric-W fidelity | Same ideal count law |
|---|---:|---|
| Canonical gate sequence | 1 | Yes |
| Independently prepared amplitudes | 1 | Yes |
| Permuted wires | 1 | Yes |
| Global phase | 1 | Yes |
| A minus sign on each of the three separate amplitudes, three fixtures | 1/9 | Yes |
| An `i` phase on one amplitude | 5/9 | Yes |
| Cube-root phases on two amplitudes | 0 | Yes |

The last state is orthogonal to the explicit symmetric W state. All nine states
have the same mathematical computational-basis probabilities. Numerical SDK
probability and fidelity errors remain below `1e-14` in the saved host evidence.
The original public wording does not define a phase convention; deciding whether
these alternatives meet that wording requires contract adjudication. This evidence
does establish that its count observable cannot enforce the explicit symmetric
state requirement.

For each circuit, six fixed count records are supplied to all seven exact top-level
assertion AST nodes from each pinned checker: **108 assertion trials**. Balanced
and inclusive-boundary records pass; lower-tail, upper-tail and incorrect-total
records fail. The first two failing tail records have nonzero probability under
ideal correct-state sampling. The outside-support record raises `AttributeError`
while constructing the original assertion's message (`result.keys()` on a circuit).
That is recorded as an error, not a successful oracle rejection.

These are assertion-slice observations. Candidate invocation, imports, sampler,
transpiler and job-result collection are excluded. No full native false pass,
actual sampled counts, isolated qualification or model execution is claimed.

## Consequence for the strengthened contract

Keep upstream replication unchanged, including these limits and its known
variability. A separately named strengthened condition must publicly declare
width, desired state/phase, admissible preparation and measurement behavior,
classical-bit mapping, tolerances and resource bounds before generation. State
preparation and measurement structure should be checked separately. A density
matrix or full-state requirement can distinguish coherence and relative phase;
sampling limits alone cannot do that, even with more shots or wider thresholds.

Do not demand a particular gate sequence or constructor merely because the
reference uses it. Correct global phases, different preparation methods and
register names/mappings permitted by the declared condition need controls. If
sampled output becomes a scored claim, preregister and calibrate its statistical
false-rejection rate and qualify the actual sampler/runtime. Host mathematics
cannot replace that qualification. Independent task admission is still required.

The [evidence bundle](artifacts/task66-sampling-diagnostic-2026-10-07/README.md)
contains exact-recreation data and tests. This is a diagnostic of one family's
requirements and observable, not a repaired scorer or completed benchmark audit.

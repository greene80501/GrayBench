# Task-62 exhaustive protected value v2

The user wants fair, auditable Qiskit HumanEval normal and hard tests. The
protected task-62 amplitude value-v1 condition has a reproduced false pass:
an input-specific wrong implementation passes its 124 cases but fails on a
valid omitted width-4 input. Its declared finite domain has exactly 1,364
binary `state`/`basis` pairs of equal width 1 through 5. The saved feasibility
probe sent all pairs through the isolated worker for three correct alternatives
and six wrong variants under the pinned Python 3.12 image. This evidence
supports building a new condition; it does not certify release readiness.

## Selected approach

Create `task62-bb84-sender-amplitudes-all-inputs-v2` with the **same public
value contract** as v1 and a separate oracle identity. The ordered private
case set exhausts every state, then every basis, for widths 1, 2, 3, 4, and 5
in lexicographic binary order. Case IDs encode width, state, and basis. The
schema permits at most 1,364 cases, and v2 validation requires exactly that
ordered set, unique call digests, binary values, and pinned task ancestry.
The v1 constructor, 124-case set, and explicit oracle selection remain
available for old evidence and ledgers. The default task-62 development
revision advances to v2 only after its tests and controls pass.

The trusted host uses the existing independent BB84 amplitude oracle. It
compares all returned values, accepts only a common global phase, and fails
when any case fails. The candidate container receives calls and its public
contract, never expected outputs. The judge manifest binds the v2 oracle,
all ordered cases, code, resource limits, and pinned image. As in v1, this
attests only returned values and cannot prove native `QuantumCircuit`
identity or a particular algorithm.

The first implementation uses the existing 120-second, 2-GiB, 2-CPU and
1-MiB-output value runner defaults. The feasibility report's largest tested
response is 533,206 bytes and all three positive implementations completed
before the probe's 60-second timeout on one machine. Those observations justify
an initial development trial, not general timing adequacy. A timeout, output limit, or
candidate execution error cannot be reported as an incorrect semantic answer
without separate resource review. Any later resource change makes a new
judge manifest and requires new evidence.

## Controls and admission

For v2, retain the three existing positive implementations and five existing
wrong variants. Add the exact input-specific mutant as a sixth wrong control;
it must fail at the omitted v1 input in both suites. The eight original
controls remain selectable for v1 replay. Run the nine v2 controls per suite
against the pinned Docker image, predeclare all judge and control identities,
and save immutable source-bound logs. Then create a successor 302-card
admission bundle with the current finding registry, old logs unchanged, new
task-62 logs and audit recomputed. The current task-62 protected-v1 finding
remains on both cards until explicit resolution review; no control result
alone marks it resolved.

## Acceptance and limits

- V1 artifacts continue to verify against their frozen source and registry.
- V2 has exactly 1,364 distinct cases for each suite, including the omitted
  v1 counterexample; tampering with one call, order, or ID is rejected.
- Three independent correct styles pass and six wrong styles fail in each
  suite under the pinned isolated runtime.
- Source-bound manifests and admission replay verify, with
  `publication_eligible: false` and no model score.
- Broader task admission, independent reviewers, provider calibration,
  prompt policy, and complete model campaigns remain separate release gates.

The alternative of random or rotating samples would retain a possible
input-specific hole and complicate reproducibility. Splitting the finite
domain across separate task scores would add aggregation semantics and could
overweight one source task. The full-domain single judge is the clearest
development condition for this particular bounded domain.

# Task 0 and task 1 oracle review

The pinned public prompts and checks were inspected in both suites. Authored
counterexamples and valid alternatives then ran through the protected upstream
judge. These are local oracle probes, not LLM generations or independent review.

## Task 0: requested circuit size

The prompt asks for a QuantumCircuit for the supplied integer qubit count. The
upstream check calls the function only with three. A function that always returns
`QuantumCircuit(3)` passes both suites, despite ignoring its argument.

The separate `qhe0-size-domain-v1` revision checks sizes 0, 1, 2, 3, 4, 7, 12 and 16.
It rejects the constant solution and accepts both pinned references. Register-based
construction and a circuit containing an H gate also pass: the prompt does not
explicitly require an empty circuit, particular register names or no classical bits.
Negative integers and noninteger inputs have no defined public behavior and are not
added as hidden requirements. Finite probes do not prove correctness for every size.

`CircuitSizeJudge` records its source, revision, original task identity and inner
protected-judge configuration. It is explicitly release-ineligible and does not
silently replace the upstream campaign track.

## Task 1: simulation and returned counts

Both upstream checks accept each of these authored returns:

- A fabricated dictionary with 500 occurrences of each Bell outcome, without running anything.
- Negative counts of -1 for both outcomes.
- Fractional counts of 0.5 for both outcomes.

The check requires the two outcome keys and a ratio between 0.4 and 0.6. It does not
establish count validity or execution of the requested pass manager, Sampler and
Aer backend. Moreover, computational-basis counts alone cannot distinguish Phi-plus
from Phi-minus; their probabilities are identical. This is an observability problem,
not just a missing numeric assertion.

The canonical solution chooses 1,000 shots, but the public prompt does not specify
that number. Requiring exactly 1,000 would introduce an undisclosed reference choice.
A corrected contract must define the statistical behavior it needs and distinguish
observable output correctness from procedural requirements that returned counts
cannot prove. No task-1 correction or certified score is claimed here.

## Evidence and remaining review

The reusable oracle-review runner stores exact case code, expected outcome,
rationale, original task digest, actual protected judgment and source identity in
exclusive append-only chained evidence. It uses the same durable started/result
workflow as reference scans, with a separate purpose label. Unexpected passes stay
visible; no candidate selection or repair is performed.

The verified task0/1 upstream replay contains12 cases: all pass, including eight
incorrect cases across the two suites. The strengthened task0 replay contains six
cases: both constant solutions fail and all four alternatives pass. Two additional
canonical reference checks pass. Earlier pre-metadata-refinement artifacts remain
preserved separately.

The inventory now surfaces these findings alongside previously reproduced issues
for tasks9,14,20,32 and35. Every task remains release-ineligible pending the complete
specification, interface, oracle, mutation and independent-review gates. Further
review of task2 type semantics and task3 measurement/drawing semantics remains open.

Verified artifact identities:

- GrayBench-v3-task0-1-upstream-oracle-review-verified.jsonl: `1b9e9018bfaca653b6d4d6543b7b122c8f01b3d31de38e1ae29404dad9477b9d`.
- GrayBench-v3-task0-strengthened-review-verified.jsonl: `f5cfb17f216b65e0626e67985b52bbf8694abb419fe47c1c6616ec2231f3db3b`.
- GrayBench-v3-task0-strengthened-reference-verified.jsonl: `584e626951c01df8468647b5e3d8ea1d83bec277206116eaeeab2ed0d9e50ea4`.

Validation:273 tests pass with Docker enabled, zero failures/errors/skips. Lint,
format and credential-value checks pass. No model API requests were made.

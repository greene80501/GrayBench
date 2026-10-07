# Protected task-2 Bell value revision: development evidence

This is a separately versioned `graybench-protected-semantic-v1` task descended
from pinned normal and hard `qiskitHumanEval/2`. It is **not** the unchanged
Qiskit HumanEval task and is not admitted for a published score. The pinned
task requests a `Statevector` but calls the candidate-returned object's
`equiv` method; a forged object can make that test pass with wrong amplitudes.
The [native probe](task2-statevector-oracle-review.md) demonstrates the issue.

The revised public task requests four complex amplitude pairs for Phi+ in
Qiskit's little-endian two-qubit order. It accepts arbitrary global phase and
declares `1e-10` absolute tolerance with zero relative tolerance. A candidate
may use Qiskit, but only the returned numeric value is judged. Neither native
`Statevector` identity nor circuit construction is attested.

| Suite | Pinned source digest | Revised public digest | Revised value contract digest |
| --- | --- | --- | --- |
| normal | `a78bfe9a998849b69a9fb0b4e781a2a1d3299e2b89948eae7842d9594f4a429f` | `d007211d9977a014c259086e74a6a2106c3ff782c5a7d778827ef1e0daf855ed` | `60dda952fe9c65d62294a3f7dae56b6b202857fa704753ff1f538147857cc529` |
| hard | `3eade3264d5638c1bd66d1a9630d9388137498b2b98e202066c3ddeb49784d88` | `fdc53438d024bce5d097c1a2d72cf8ac00ceaf5ff823f5659e92028611502277` | `172e8f342a159c0b9c009229ed7ab46c126173177de5f5f6235d725f05ee6fc8` |

The candidate container receives one no-argument call and returns a
shape-checked JSON value. The trusted host checks finite values, unit norm,
nonzero overlap, and all amplitudes after global-phase alignment. The tested
positive controls are direct mathematical construction, a Qiskit H/CX circuit
converted to amplitudes, and a globally phased state. Negative controls include
Phi-minus, product and wrong basis states, an unnormalized state, malformed
shape, extreme amplitudes, and forged verdict text. A two-task campaign with
task 20 also generated and judged both answers successfully for normal and
hard; all 149 other task IDs were frozen as exclusions in each suite. Focused
verification on the pinned Python 3.12 image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`:
`pytest tests/test_protected_task2.py tests/test_protected_campaign.py -q`;
24 passed on 2026-09-27.

The full engine suite passed locally: 1,244 passed, 5 skipped, and 6 expected
failures in 590.95 seconds. Ruff check and format check passed. A separate
read-only code review found no actionable finding in this revision.

These authored controls are public and do not constitute an unseen holdout or
independent Qiskit review. The task card remains pending, release eligibility
is false, and no protected model score follows. Admission needs separate domain
review, frozen case review, and independent reproduction.

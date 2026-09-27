# Tasks 137 and 138: undisclosed list length and a threshold mismatch

Task 137 asks for a dataset of two-qubit density matrices with entanglement of
formation greater than or equal to the supplied tolerance. Task 138 asks for a
list of density matrices whose mutual information is **greater than** the
supplied tolerance. Neither public prompt gives a list length; both pinned
tests require exactly ten elements.

The [12-case protected-bridge probe](task137_138_oracle_probe.py) uses
deterministic valid density matrices with the unmodified normal and hard
tests in the Python 3.12 / Qiskit 2.4.2 evaluator image. A ten-element list
of Bell density matrices passes both tasks and suites. A three-element list
of the same qualifying matrices fails both tasks and suites solely at the
length assertion. "Dataset" may imply a collection, but it does not specify
ten; the correct release contract must set a length before generation.

The task-138 test uses `mutual_information(item) >= tol` despite the strict
`>` in the prompt. A valid classically correlated matrix with mutual
information exactly 1.0 passes at the tested tolerance of 1.0 in both
suites. A maximally mixed matrix with zero mutual information fails both.
This is a definite false acceptance against the prompt's inequality, separate
from the count ambiguity.
The [saved twelve-case result](GrayBench-task137-138-oracle-probe.json) has
SHA-256 `81ae3bf0b2265dc22f357deffd579301d639b519c02cc7eb08fc751639c14add`.
It records dataset and task digests, candidate and judge digests, exact outcomes,
runtime versions, and measured entanglement and mutual-information values. No
model or external service was called.

The pinned upstream tests remain unchanged for historical reproduction.
Neither task is admitted for verified scoring. A separate semantic release
must state output cardinality and tolerance domain and test the declared
inequality without requiring the reference's random construction or unique
matrix values.

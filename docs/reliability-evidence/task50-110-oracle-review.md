# Tasks 50 and 110: untested position and vacuous empty result

Task 50 asks to remove the gate at the supplied position. Both pinned tests
use position zero only. The [paired probe](task50_110_oracle_probe.py) shows
that a function that always removes the first gate passes both suites, while
an unchanged-circuit control fails. On a valid position-one input, the mutant
removes the first `h` rather than the requested `cx`. The canonical solution
passes both tests when run natively in one Python namespace, but the current
protected proxy reports `unsupported` for it because it mutates the input
circuit. This is an interface fidelity limit in addition to the weak oracle.

Task 110 asks for a list of `n` equivalent Clifford circuits. Its pinned test
iterates over returned items without checking the list length. An empty list
passes both suites for `n=10`; a ten-item list of copies of the supplied
Clifford also passes; a non-Clifford control fails. The copied input is a
checker control, not evidence that the requested random generation occurred.
The potentially unbounded canonical random search was not run in this probe.
The [saved twelve-case result](GrayBench-task50-110-oracle-probe.json) has
SHA-256 `1e8ae74678e45f2eb86bb5b129af34fed27bc20d2b8ea1e04e7b7c5b96cdeaf0`.
It includes two native reference checks, the position-one witness, dataset
and task digests, candidate and judge digests, and runtime identities. No
model or external service was called.

The original upstream tests remain unchanged. A separately versioned release
must exercise multiple positions and declare mutation semantics for task 50,
then validate both list cardinality and every item for task 110. Both families
remain release-ineligible; these diagnostics are not model scores.

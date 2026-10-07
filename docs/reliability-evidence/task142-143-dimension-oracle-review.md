# Tasks 142 and 143: one-qubit requirements are unchecked

Task 142 requests ten one-qubit density matrices with purity strictly above
`0.5`. Its test checks the list length, `DensityMatrix` type, and purity
`>= 0.5`, but never checks dimensions. Task 143 requests ten pairs of
one-qubit statevectors with fidelity strictly above `0.9`. Its test checks
list length, `Statevector` type, and fidelity `>= 0.9`, but also never checks
dimensions. The fidelity boundary was not probed in this review.

The [exact-test probe](task142_143_oracle_probe.py) ran 22 authored cases
against the unmodified normal and hard tests in the immutable Python 3.12.14
/ Qiskit 2.4.2 image with network disabled. Both canonical references passed.
For task 142, ten pure **two-qubit** matrices passed, as did ten maximally
mixed one-qubit matrices with purity exactly `0.5`. A valid pure one-qubit
alternative passed, while low-purity and wrong-length controls failed. For
task 143, ten identical **two-qubit** statevector pairs passed, as did valid
one-qubit pairs; orthogonal and wrong-length controls failed. Each normal
`check` was invoked explicitly; each hard test invokes it itself. No model
API request was made.

The [saved UTF-8 result](GrayBench-task142-143-exact-oracle-probe.json) has
SHA-256 `33c7314e4f3cd27b67718c1a24a3290debd5f24919722a4e05fdd869fdd07577`.
It binds the source, dataset pins, task digests, candidate hashes, runtime
and outcomes. This is authored native diagnostic evidence, not a protected
judge run or benchmark score.

A separately versioned semantic contract should check dimensions explicitly
and implement the declared strict comparison for purity. The task 143
fidelity boundary should be specified and checked independently. Do not infer
that duplicate values are invalid: neither prompt requires distinctness or
random draws. Keep the historical upstream tests unchanged; neither task is
admitted for a verified score.

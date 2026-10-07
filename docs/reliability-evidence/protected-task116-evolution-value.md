# Task 116: separate protected evolution matrix values

This development condition scores submitted complex matrix values for Pauli
evolution. It does not replace either original Qiskit HumanEval task 116 or its
native/graph conditions. The original task returns a circuit and asks for a
synthesis technique; this revision explicitly permits equivalent algorithms and
changes the answer interface to JSON-compatible values. Its scores must be
reported separately. No task has been admitted for publication by this change.

The constructor accepts only the exact pinned normal and hard source records:
`e91d1fdee6400859d41d0ec5ba98da055ebd8978f3ef0a63c555b858fc3a151c`
and `548733e9c66ce4a782794d7cd3aeff29e38624e563f6eedd102c9479d320f2a6`.
The new oracle is `task116-pauli-evolution-matrix-values-v1`.

## Public contract and information

`evolution_matrix(pauli_string, time)` accepts unsigned Pauli strings of one
through five I/X/Y/Z letters and finite real time. It returns the matrix of
`exp(-i*time*P)` as nested Python lists, with each entry `[real, imaginary]`.
The rightmost letter acts on qubit zero; rows and columns follow ascending
computational basis indices. Maximum absolute complex-entry error is `1e-10`,
with zero relative tolerance. Global phase is retained, including all-I inputs.
Boolean, nonfinite and nonnumeric components are invalid. Finite numerical
answers with excessively large error fail rather than crashing the judge.

Normal supplies a function prefix and contract docstring. Hard supplies the
same requirements and entry point without implementation imports or a prefix.
Neither supplies a formula for computing the answer, canonical code, private
cases or test feedback. Tests check both revised prompts through all five
built-in adapters without contacting providers. The revision is deliberately
more explicit than the original and is not a published QHE replication.

## Judgment and controls

The trusted oracle computes each Pauli's basis-index permutation and complex
phase directly. It does not extract a submitted circuit, use an SDK matrix
conversion, build tensor matrices or run an eigensolver. Only the returned
numeric values are attested; native identity, storage and synthesis are not.
The strict existing value parser precedes numerical judgment. A candidate may
manipulate its own worker, but cannot turn a returned wrong value into a pass
by printing a verdict; trusted scoring remains outside that worker.

The ordered roster contains 80 calls: the original 16 action probes, all width
one/two unsigned Pauli tensors at three times after deduplication, and eight
width-five probes. Width counts are 15, 53, 2, 2 and 8. The complete ordered case
IDs and serialized call digests are validated. Python equality is insufficient:
substituting `False` for `0.0` is rejected. Manifests bind both the independent
oracle module and the public contract module, as well as existing worker and
execution identities. No calls can be dropped after seeing answers.

Fifteen authored controls per suite are declared before execution:

- Three correct alternatives: original canonical Qiskit computation followed
  by explicit matrix export, literal tensor eigendecomposition, and a circuit
  using basis changes, parity operations and rotations.
- Ten valid but wrong answers: identity, reversed time, doubled time, reversed
  tensor order, transpose, conjugation, extra phase, missing all-I phase,
  scaling, and enormous finite components whose complex error overflows.
- Two invalid outputs: an empty result and an unserialized ndarray.

The production CLI can predeclare and run these controls with an immutable
container image once Docker is available:

```sh
cd engine
uv run --locked graybench protected-oracle-review CACHE NEW_REVIEW.jsonl --suite both --task 116 --image sha256:IMAGE_DIGEST
uv run --locked graybench oracle-review-inspect NEW_REVIEW.jsonl CACHE
```

Protected planning supports explicit task-116 selection through the existing
registry. Other tasks retain their exclusions. Default control selection is
unchanged. Shared semantic-judge code changes its manifest hash, so prior judge
evidence remains historical rather than becoming evidence for this source.

## Evidence and limits

The [local calibration bundle](artifacts/evolution-value-calibration-2026-10-07/README.md)
executes only trusted authored fixtures through the real worker/parser and
checks the oracle against independently constructed literal tensor matrices.
Local subprocess execution here is not sandbox qualification and must not be
used for model-generated code. The container regression remains pending.

Finite cases do not cover the entire real-time domain or every allowed tensor
at every time. The five-qubit limit, output allowance and timeout are declared
resource choices, not equivalence to unbounded circuit output. Independent task
reviews, source-current admission, isolated controls and campaign qualification
remain required before ranking models.

The original canonical graph transport is still
[unsupported for its observed Rust-owned allocation](artifacts/canonical-evolution-transport-2026-10-07/README.md).
Exporting a matrix inside a candidate worker avoids that representation in this
separate value condition; it does not repair native-object transport or prove
native reconstruction fidelity. Historical artifacts and scores are unchanged.

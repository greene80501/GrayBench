# Task12: explicit complete Bell operator

## Problem and condition choice

The exact pinned normal and hard prompts ask for a phi-plus Bell circuit matrix,
but their checks require the particular operator H on qubit 0 followed by CX(0,1).
Other circuits can prepare the same Bell state from zero while acting differently
on other inputs. The preserved
[source diagnostic](artifacts/task12-operator-ambiguity-2026-10-07/README.md)
demonstrates this ambiguity. Its original task bytes and observations remain historical.

`qhe12-explicit-bell-operator-values-v1` is a separate development condition.
Its public prompt specifies H0 then CX(0,1), basis order `|q1 q0>`, row/output and
column/input conventions, complete four-column action, return type, numeric widths,
phase alignment and comparison tolerance. Every provider receives this same public
contract within a suite; normal retains function-completion scaffolding and hard
requires a standalone function. Exact source digests bind each ancestor, and any
different prompt, test, canonical answer or other source field is refused. The
revision is idempotent and must be applied before request preparation and judgment.

This resolves the hidden operator requirement by making it public. It changes the
information supplied to models, so its scores must remain separate from pinned
upstream scores and published baselines. It does not prove construction methods.
No expected matrix, control completion or private checker enters a provider request.

## Oracle and transport

The private oracle derives I tensor H in the declared basis convention and builds
CX from basis indices, independently of the candidate and the SDK simulator.
All 16 entries are checked. Overall phase uses the normalized, nonzero Frobenius
inner product `sum(conjugate(expected_entry) * returned_entry)`. Entry comparisons
then use absolute tolerance `1e-10` and zero relative tolerance. This particular
alignment rule is public; it is not a claim to solve every possible minimax phase
fit. Scaled, transposed, partially correct and relative-column-phase matrices fail.

An independent review found that a graph transport prototype imposed hidden array
ownership requirements: correct external-buffer, dtype-metadata and large-backing
views were rejected. The final condition uses existing protected **logical value**
protocol 3. A no-argument matrix result has no input mutation or ownership contract
to preserve. The codec transfers logical entries in C order, with dtype and shape,
without copying the whole backing allocation or claiming to preserve aliases,
strides, metadata or writeability. This is not a fallback from a graph contract.
The unpublished graph prototype is not a registered condition.

The portable numeric domain is signed/unsigned integers of 8/16/32/64 bits,
real floats of 16/32/64 bits and complex floats of 64/128 bits, either byte order.
Exact plain ndarray type is required; object, subclass and extended-precision
arrays are outside this profile. Accepted dtype widths do not relax accuracy:
many low-precision approximations fail the tolerance, while an exactly representable
complex64 phase variant passes. Numeric dtype metadata does not change values.
The codec preserves the supported logical numeric bits; it does not round answers
to make them pass. Invalid extreme entries are bounded before phase arithmetic,
and Python complex accumulation avoids NumPy underflow exceptions during overlap
calculation. None of these host checks establishes candidate-side encoder integrity.

Review also reproduced a unitary with equal and opposite tiny column phase errors:
each entry was within the stated tolerance of the target, but the initial private
single-entry phase rule rejected it. The final symmetric, public rule accepts that
case. The regression was observed failing before the correction and passing afterward.

## Verification and remaining gates

The [current evidence bundle](artifacts/task12-explicit-operator-2026-10-07/README.md)
contains a durable plan written before execution, exact-recreation host evidence,
focused/full JUnit results and clean-checkout reproduction. Fixed authored controls
cover both formats. Independent basis-action derivation is compared with the SDK,
257 global phases are accepted, and 32 mutations separately alter every real or
imaginary matrix entry and are rejected. These are finite controls, not an
exhaustive floating-point proof or an independently admitted benchmark.

`task12_controls.py` predeclares the isolated semantic roster and manifests before
launching any candidate. Its 56 cases comprise 30 passes and 26 failures. Two
additional object-array cases appear only in the host codec screen as unsupported;
an unsupported transport outcome is not silently counted as an oracle rejection.

Docker remains unavailable. The full isolated semantic roster, resource calibration,
adversarial encoder controls and independent human contract/oracle admission must
still pass before release. The judge therefore always reports `release_eligible=false`
and unqualified runtime status. There are no new model generations or model scores.

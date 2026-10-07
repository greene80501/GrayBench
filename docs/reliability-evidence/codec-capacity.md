# Codec capacity is not model correctness

A valid Qiskit object can exceed the evaluator's bounded representation. For example,
a Gate with a 5,000-character label is valid but exceeds the decoder's label cap.
Previously that returned object could be classified as candidate_error. The decoder
now uses a distinct WireLimitError for the covered capacity checks. The host bridge,
upstream judge and protected semantic judge map that exception to unsupported.
The protected judge also treats its input-byte cap as unsupported.

Covered checks include circuit and plain instruction names/labels, circuit metadata,
operation/definition budgets, compressed circuit bytes, bounded integer allocation,
generic parameter count and outer value nesting/structural budgets. Malformed types,
invalid schemas and inconsistent compressed streams remain typed-data errors. A
capacity exception cannot produce a pass; unsupported outcomes retain the existing
summary blockers rather than shrinking the frozen cohort denominator.

This is a bounded repair, not a claim that every codec limit is audited. Scientific,
symbolic and preparation-specific checks still contain combined validity/capacity
conditions and need separate review and adversarial tests. Exceeding capacity does
not establish that an answer is correct or even fully valid; it establishes that
this evaluator cannot reach a correctness conclusion under its current limits.

Regression tests exercise real isolated upstream and protected judge processes,
valid long labels on circuits and standalone instructions, malformed label types,
the input-byte cap, compressed error propagation and the host decoder mapping.
No candidate receives hidden tests or correction feedback. No model generation
calls are required for these checks.

Validation after restoring Docker: 300 tests passed in 98.00 seconds, with zero
failures/errors/skips, recorded in GrayBench-v3-codec-capacity-recovered-tests.xml.
Ruff lint/format and the credential-value diff scan passed. Earlier reports are
preserved: the initial run had one obsolete exception expectation; the next had
one missing test import, subsequently fixed; the September 19 run while Docker
was stopped had 55 infrastructure-related test failures. No model API calls were made.

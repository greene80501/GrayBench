# Reconstruction outcomes (in progress)

The task 72 control-flow replay exposed a classification defect: native owner
reconstruction could fail for a valid reference solution, yet the trusted bridge
classified it as candidate_error. The ledger scores candidate_error as a failed
sample; infrastructure_error blocks scoring.

GraphReconstructionError distinguishes owner reconstruction failures: an existing
object cannot bind to a newly exported native cache, bound caches are invalidated,
new unbound objects appear, or reconstructed state differs from its declaration.
It remains a WireError subclass, with explicit infrastructure_error handling before
generic wire validation handlers. The fatal bridge marker overrides private tests
that catch BaseException. Generic unexpected ValueError and TypeError now reach
that fatal guard instead of being classified as candidate errors.

Protected tests cover owner invariant injections, ledger score blocking, outgoing
snapshot errors, six generic error/phase combinations, legitimate candidate
RuntimeError/ValueError/TypeError, and five malformed envelopes that must still
produce candidate_error. A native-valid two-call test exports a circuit qubit list
before its owner: reconstruction remains unsupported in practice, but cannot be
scored as a model failure. Actual late-owner alias support remains required.

## Preserved fault evidence

These are controlled transport fault fixtures, not model scores. Both files have
six identical case identities and verified complete hash chains. The after scan
source manifest exactly matched runtime bytes when inspected.

- GrayBench-v4-bridge-classification-before.jsonl: one infrastructure_error, one
  unsupported, four candidate_error. SHA256
  c093a1c52084f1e9e50edc54a18043b1cd229e0a2579d1bcf2475d293f45792a.
- GrayBench-v4-bridge-classification-after.jsonl: all six infrastructure_error.
  SHA256 c1dc0b3bd4a04e8d09c7277f57fbe5dec2ae327ebb23f54380955315de6b4d33.

Earlier full regression: 875 passed, before the generic exception refinement and
late-owner test. Final protected regression: 884 passed in 350.75 seconds, with zero failures,
errors or skips. All 39 focused fault/bridge tests passed. Ruff lint/format
(129 files), whitespace and secret-value checks passed. The earlier report does
not certify this final implementation; the final report is
GrayBench-v4-reconstruction-final-tests.xml. This change does not establish complete
protocol support, full benchmark admission, or a certified model score.

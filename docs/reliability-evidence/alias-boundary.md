# Identity changes verdicts in the current value-only bridge

This is an unresolved correctness defect, not only missing mutation support.
The protected bridge serializes each value separately. It can therefore change
whether arguments refer to the same object, whether a result is the original input,
and whether a later call receives an object seen earlier. Comparing before/after
serialized values does not detect replacement by an equal-valued different object.

Six trusted authored synthetic probes were run directly as ordinary Python and
through the protected candidate/oracle containers on source 1d0ce1f (actual
worktree byte hashes retained). They show one false acceptance and five false
rejections relative to native execution:

| Probe | Native | Current bridge |
|---|---|---|
| Correct `a is b`, same list passed twice | pass | fail |
| Incorrect `a is not b`, same list passed twice | fail | pass |
| Correct identity across positional/keyword arguments | pass | fail |
| Return the original input object | pass | fail |
| Replace a nested list with a new equal-valued list | pass | fail |
| Recognize the same argument object across two calls | pass | fail |

[Raw protected evidence](GrayBench-v3-alias-boundary-diagnostic.jsonl), SHA-256:
`a6f312247718ca288cf578d2c78edbb6cf52fb5addda0c844caa511e68135686`.
The log contains the full authored functions, assertions, native outcomes,
protected transcripts, source identities and immutable image. Native probes ran
on the host's pinned engine environment; candidate/oracle probes ran in isolated
containers. Only trusted authored fixture code was executed natively. These are
synthetic interface diagnostics, not actual LLM samples or benchmark scores.

The record's expected_current_bridge_outcome records a reproduced defect; matching
that outcome is not a correctness success. None of these six defects is fixed by
this research commit. Legacy source-bound evidence remains preserved. Existing
release-ineligible status must remain in force; value-only outcomes cannot certify
identity-sensitive Python task behavior.

## Root cause

- `value_wire.encode` serializes lists/tuples/dictionaries recursively without an
  object-reference table. Repeated objects become independent values.
- `worker.py` decodes positional and keyword arguments separately and encodes the
  result and two post-call snapshots separately.
- `upstream_process.py` only compares serialized before/after values. It rejects
  visible mutation but misses graph-topology changes with equal values.
- `sandbox.py` reconstructs returned values and argument snapshots independently.
- Each call creates new argument objects, despite keeping the candidate process
  alive, so candidate globals cannot recognize a previously supplied object.

A shallow assignment of returned circuit state would leave these defects intact.
The [graph protocol design](../superpowers/specs/2026-09-19-call-object-graph.md)
and [implementation plan](../superpowers/plans/2026-09-19-call-object-graph.md)
cover the required replacement. They are implementation work still to be completed,
not a declaration of support or scientific certification.

Task147's explicit unsupported-mutation result is only one visible symptom.
Tasks50/63/72/73 also require input mutation, with task72 relying on it without
using a return value. Task63 additionally seeds RNG only in the private test;
a graph transport must not copy the judge's RNG/global state into the candidate
to make that reference pass. That is a separate oracle-contract issue to review.

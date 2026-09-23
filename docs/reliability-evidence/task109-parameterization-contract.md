# Task 109: preserving valid parameterizations

This extends the [oracle audit](task109-oracle-review.md) with controls against
an unfair repair. The public prompt specifies neither a parameter interval nor
a relationship between parameter value and azimuth. A revised evaluator must
not silently assume either from the reference implementation.

For a circuit consisting of H followed by RZ(f(t)), direct multiplication gives
the Bloch vector `(cos(f(t)), sin(f(t)), 0)`. Overall complex phase does not change
this vector. This relation independently explains the following controls:

| Parameter expression | Physical coverage for real t | Consequence for an oracle |
|---|---|---|
| `t` | Entire equator | Canonical positive control |
| `t / 1000` | Entire equator, traversed slowly | A fixed small interval is insufficient evidence of missing coverage |
| `4 * t` | Entire equator, traversed repeatedly | Samples at 0, pi/2, pi and 3pi/2 all coincide; those samples alone falsely suggest a constant circuit |
| `sin(t)` | Only azimuths in [-1,1] radians | Variation and a nonzero parameter count do not establish full coverage |

The slow and fourfold constructions use the same one-qubit, one-parameter,
two-instruction shape as the reference. They change only the parameter expression.
They should not be rejected merely for using a different parameter scale. This
does not settle the prompt's ambiguous phrase "minimum resources": the allowed
gate basis, decomposition cost and objective were never specified.

## Verified native experiment

`task109_parameterization_probe.py` extends the corrected previous probe with
these three cases. Seven fixtures in each suite execute the exact pinned check
body once, with exactly 1,000 counted candidate calls. All 14 cases pass upstream,
including the short-arc mutant. Both suites' check bodies, extraction conditions
and task/source hashes are preserved. No private RNG state is supplied to a model.

The four recorded Bloch witnesses confirm the expected sampling problem: the
fourfold circuit has the same vector at all four selected points; the slow
circuit varies only slightly; the short-arc circuit varies but cannot reach the
negative-X hemisphere, since cos(sin(t)) is at least cos(1), which is positive.
The analytic statement applies to real t; the finite witnesses alone are not a
proof over that whole domain.

- Raw: `GrayBench-task109-parameterizations-0379d13.jsonl`
- SHA256: `567bee29051760514882400e47e41eb096813fdd8fb8fc5476a559edd19715d3`
- Chain: `d26d7f62e4d718c4dc557ba7347f01e3383fb5859e3430fbde400d5a58356ffa`
- Probe SHA256: `f7618453a5f99f07a5c66f6fb039cdf1577878aa74d3e4e5719905fd88f0b158`

Run from `engine/` using the same explicit cache layout as the earlier probe:

```sh
uv run --extra qiskit --extra dataset python ../docs/reliability-evidence/task109_parameterization_probe.py NEW_OUTPUT.jsonl
uv run graybench reference-inspect NEW_OUTPUT.jsonl
```

This is trusted local oracle evidence, not a protected-runtime result, model
measurement or task-admission certificate. The protected full reference workload
is independent. No performance conclusion uses these concurrent local probes.

## Decision for a fair revision

Keep the exact upstream test as an explicitly historical condition. Do not
repair it by requiring a particular parameter name, linear scale, four-point
variation, sampled angular spread, or the reference's gate spelling. Each would
confuse a testing convenience with a public requirement.

A future revision has two honest choices:

1. Retain unrestricted parameterization and report the limits of finite coverage
   evidence. Include independently justified alternatives and adversarial
   parameterizations; do not call a sampling heuristic a proof of coverage.
2. Publish a changed behavioral contract that defines the parameter domain and
   required input-to-state relationship before generation. Then test that
   relationship, accepting equivalent gates and global phases. Label results as
   that changed condition rather than full replication of the original task.

Neither option settles the unspecified resource objective by itself. An explicit
resource contract and review are still needed. This audit chooses no new scoring
rule and does not change prompts, defaults or historical verdicts. It supplies
positive and negative controls that the eventual design must address, preserving
the goal of testing any valid implementation without hidden assistance or penalties.

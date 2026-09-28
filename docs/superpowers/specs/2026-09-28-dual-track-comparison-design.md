# Dual-track development comparison

## Intent

GrayBench's paired-family comparison currently accepts only the historical
`CampaignSetup` task shape. Native and protected campaigns can write complete
ledgers and summaries, but operators cannot freeze and verify a paired
comparison through the CLI. The user asked for auditable normal/hard benchmark
reporting without silently treating different test contracts as equivalent.

This extension retains the existing `ComparisonPlan` and bootstrap method,
including its development-only status. It adds explicit track-aware task and
setup validation. It neither admits tasks nor publishes model rankings.

## Approaches

1. Compare only ledger summaries. This is small, but loses source-task and
   public-request reconstruction, so a mislabeled setup could appear paired.
2. Create separate native and protected comparison engines. This gives clear
   types but duplicates metric and uncertainty code, risking divergent rules.
3. **Extend the current plan's binding layer by track.** Keep one statistical
   implementation and validate each setup with its own existing cohort rules.
   This is the selected approach.

## Binding and compatibility

`make_plan` and `compare_runs` continue to accept historical `JudgeTask`
records. For the native track they accept the same record shape and recompute
the frozen dataset digest and every public prepared request. For the protected
track they accept `ProtectedSemanticTask` records, use `task.contract.public`
for requests and family IDs, and compute the dataset digest from both the
source-task and revised-task digests in the existing protected cohort shape.
Every task key and family must match the frozen protocol. The two protocols
must have the same track, task set, denominator, extraction, judge, runtime,
exception policy, population, exclusion map, timing, source and analysis
identities. Model specifications and request digests can differ and remain
visible in the plan; a free-text configuration comparison cannot certify
effective equivalence.

The CLI reads the setup's frozen protocol track and validates against exactly
one of `CampaignSetup`, `NativeCampaignSetup`, or `ProtectedCampaignSetup`.
Both sides use the same setup type. Existing setup and comparison JSON stays
readable; no schema or digest field changes are needed. Plan creation validates
each setup against pinned source data, then writes exclusively to a new file.
Comparison reloads stored run contexts, verifies their setup protocols,
validates pinned ancestry, and checks the plan against the ledgers in one
read-only reporting flow. A mismatch is an error, not an unpaired score.

## Report semantics and tests

The point estimate remains the left-minus-right pass fraction over the frozen
sample denominator. Bootstrap draws entire task families, preserving the
existing unequal-family weighting and its small-sample interval blockers.
Incomplete or unscorable run summaries return `unscored`; complete reports
remain `development_only` and `publication_eligible: false`. Normal and hard
are never pooled, nor are native and protected results.

Tests cover native and protected plan creation and report generation, wrong
task ancestry, mixed tracks, changed extraction/exception policy, incomplete
ledgers, stale source, and historical plan identity. No provider call is needed.
The full pinned Python 3.12/Qiskit Docker suite and independent review remain
the verification gate. Both GitHub Actions workflows stay disabled while the
account has exhausted its included minutes.

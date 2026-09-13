# Frozen-denominator development reports

Ledger summaries now derive their denominator from the frozen task keys and repeat
count. Missing or unexpected sample rows block a score instead of changing the
denominator. Reports include each task's replicate outcomes, counts for every
judgment category, absent/unexpected schedule slots and explicit score blockers.
Unsupported interfaces and infrastructure errors remain distinct from model
failures. Pending generations and judgments remain visible.

The summary checks stored blob hashes, event-chain continuity and foreign-key
relationships before computing a report. All queries run in one SQLite read
snapshot so concurrent generation or judgment cannot mix different database states
inside a single report. This does not authenticate every relational row against
an externally anchored event history or protect against a malicious database owner.

The current engine source digest must match the protocol's frozen analysis digest
to produce `pass_at_1`. A source mismatch still permits diagnostic counts and
provenance inspection, but withholds the score. The setup builder already binds
the entire engine source to this digest; this is deliberately conservative. To
reproduce an older report, use its original source environment. No automatic
migration, changed denominator or revised analysis is silently substituted.

For complete balanced cohorts, the development estimate is the mean single-attempt
success across the frozen task/replicate slots. Repeated samples do not become a
best-of-N score. This report provides no confidence interval or independence claim;
paired model comparisons and task-cluster uncertainty remain separate required work.

Complete reports are labeled `development_only`; incomplete or incompatible
reports are `unscored`. Publication eligibility remains false pending reviewed
task/protocol admission and independent reproducibility. Numeric completeness
does not certify an oracle, effective model configuration or published comparison.

Regression checks cover repeated-sample arithmetic, a missing schedule row, an
unexpected row, distinct unscored outcomes, corrupted evidence, analysis-source
mismatch and a writer committing a judgment during summary generation. The
concurrent report retains the earlier snapshot; the next report sees the commit.

Validation:254 tests pass with Docker checks enabled, zero failures/errors/skips;
Ruff lint/format and the credential-value diff scan pass. No API generations were
used for this change.

# Paired comparison for native and protected development runs

The original `comparison-plan` and `compare` commands accepted historical
evaluation-recipe setups only. Native and protected ledgers could be summarized
individually but lacked the same frozen paired-family analysis path. The CLI
now selects the setup contract from its protocol track and validates both
setups against the pinned cache before writing a plan. On reporting, it reloads
the setup from each durable run context, checks it against the planned
protocol, verifies its cohort ancestry, and compares verified ledger summaries.
Mixed tracks, suites, populations, exclusions, extraction conditions, native
exception policies, judge identities, and denominators are rejected.

The historical and native tracks bind `JudgeTask` digests and public requests.
The protected track binds both source-task and revised-task digests, then
regenerates each public request from the revised value contract. Task families
are taken from those same bound public records. The existing paired-family
bootstrap and left-minus-right pass fraction are unchanged. A complete pair
is labeled `development_only`, never publication-eligible; either incomplete
or unscorable run yields `unscored` with no comparison value. A one-family
fixture reports the point difference but no confidence interval.

Local HTTPX fixture tests on the pinned Python 3.12/Qiskit Docker image ran
one native and one protected task family through two complete ledgers each:
one accepted answer and one deliberately wrong answer. Both CLI comparisons
returned a left-minus-right fraction of 1, an unavailable interval reason of
`fewer_than_two_families`, and `publication_eligible: false`. Other tests
reject a forged protected source digest, mixed setup kinds, altered stored
context, and output overwrite. These are mechanism checks, not model scores.

The operator's `configuration_comparison` text records an assessment but
does not verify equal effective provider settings or weights. Different
models and provider adapters may have different defaults even when the frozen
request bodies appear comparable. Task admission, independent oracle review,
provider calibration, external authenticity, and clean-machine reproduction
still block release. Normal and hard suites, and native and protected tracks,
must be reported separately. An older archived comparison fixture omits
later `ModelSpec` defaults: its raw canonical plan still hashes to its saved
digest, but parsing it under the current model can add default fields. Its
historical report must not be silently reissued as a current-source score.

Both GitHub Actions workflows remain manually disabled while the account has
exhausted its included Actions minutes. Local tests are reported separately
from CI.

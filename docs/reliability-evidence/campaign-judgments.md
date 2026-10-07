# Bound upstream campaign and durable judgment scheduling

UpstreamJudge.configuration(task) exposes the exact payload identity and execution manifest
without running candidate code. A cohort binds the complete task-record digest map, each task's
judge-manifest digest, and immutable runtime image. The cohort judge identity is distinct from
individual task judge identities; both are retained in judgment evidence.

validate_cohort also regenerates public requests through the declared adapter and compares every
request digest to the protocol. Tests/references are not given to provider request construction.
UpstreamCampaign performs these checks before generation or judgment, then connects the durable
generation component to the protected upstream judge.

The append-only judgment_claims table commits evaluation intent before candidate execution.
An interruption leaves a pending claim and stops resume rather than rerolling a stochastic test.
Ordinary judge failures become unscored infrastructure outcomes with exception type only.
No saved answer is regenerated as part of judgment recovery.

An integration check uses two mock HTTP generations and the real protected Docker judge: correct
and incorrect functions produce one pass and one fail, exactly two generations, immutable claims,
and a verified ledger chain. The reported 0.5 is a synthetic fixture result and remains uncertified.
Other tests verify pre-dispatch task/runtime/request mismatch rejection and interrupted judgment
behavior. No billable provider requests were made.

These checks establish identity consistency, not task adequacy. Complete review/eligibility
admission, independent oracle validation, model identity drift policy, campaign CLI and statistical
reporting remain release requirements. Runtime identity currently denotes the immutable image;
host/package provenance binding needs to be included in the finalized campaign admission record.

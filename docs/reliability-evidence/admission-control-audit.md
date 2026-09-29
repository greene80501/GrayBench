# Local admission-control coverage

The protected-track inventory is a durable review checklist for all 302 pinned
normal and hard records. Schema 2 retains the source digest of the engine that
created it but validates task ancestry against the exact pinned parquet bytes,
so an unrelated later engine edit does not erase accumulated task-card work.
Schema 1 keeps its historical current-source validation rule. Neither schema
authenticates its author or makes a card publishable.
Legacy JSON without an explicit version still parses as schema 1.

`admission-control-audit` inspects each supplied authored oracle-review JSONL
file, verifies its event chain and pinned case ancestry, and joins its controls
to the matching cards. The report includes every card, even when it has no
controls. It cites artifact and case digests and records both expected and
actual outcomes. Schema 2 also lists each task-card requirement's claimed
evidence links. A positive-alternative claim has a matching local observation
only when every logged instance of that case expected and produced `pass`; a
wrong-mutant claim similarly requires `fail`. Missing references and conflicting
or opposite outcomes are explicit. Oracle-case references remain
`unverified_fixture`: these logs identify candidate completions, not individual
protected test fixtures. The earlier schema-1 report remains historical evidence.

These are consistency checks on authored local observations, not proof that an
alternative is independent, a mutant is semantically wrong, a requirement is
covered, or the revised public contract matches the exercised judge. One
observed pass does not establish correctness and one observed failure does not
establish a sufficient oracle. The audit cannot prove the logged judge ran or
authenticate an unsigned evidence chain. Valid-input review, mutation adequacy,
oracle-fixture evidence and two independent qualified reviews remain separate
obligations. All cards and reports remain `publication_eligible: false`.

Using the saved task-0/1 upstream and strengthened task-0 artifacts, the local
report contains 18 controls across 4 cards. The other 298 cards have no controls
from those two files. Eight authored wrong-answer controls unexpectedly pass the
upstream tests; there are no authored correct-control failures or other
mismatches. All six strengthened task-0 controls match expectation. These
original artifacts were local outputs. The exact inventory and control-log
bytes are now in the [admission evidence bundle](artifacts/admission-2026-09-28/README.md)
for repeat inspection. The inventory and report identities are:

- Schema-2 inventory: `3c924f9a4a09e8fb083a4913df21b1f9dbcab0ae0fd48bcbe76c1efe1ed613ce` (model identity).
- Control audit: `13693c8b931b105e85fb171de3b9207d4ae32eb6ec498afacffad74b01185b5e` (file SHA-256).

The schema-2 audit of the same local logs is
`GrayBench-v3-admission-control-audit-v3-20260928.json`, SHA-256
`6bb133cbaad2d43acfdf36ea6868b507b99a4b7468820b37ae319fbb782834d7`.
It again reports 18 controls, 4 covered cards, 298 uncovered cards and 8
false passes. The pending inventory contains no requirement evidence claims yet,
so its new `evidence_links` lists are empty. That historical report remains
outside the PR; the saved inventory and control logs are bundled.
All artifacts and all 302 cards remain `publication_eligible: false`.

## Judge-condition binding (report schema 4)

The previous audit linked a candidate-control digest to a protected-track
requirement without checking which judge or public contract produced the
outcome. That could make an upstream test appear to support a revised protected
oracle. Merely matching the public contract is also insufficient: task 20's
three-layout and all-layouts oracles share one contract. Schema 4 checks a
recorded judge manifest against its judge digest and requires the card to bind
that exact protected judge digest, as well as the track and public contract.
The full judge digest covers the oracle, private cases, code hashes and runtime
configuration. Missing manifests, upstream judges, different contracts and
different oracle versions remain visible as controls but receive
`unqualified_judge_condition`. A missing judge binding is an admission blocker.
Old pending card identities are preserved by omitting the absent optional
binding when serialized. Matching claims are still local, unsigned evidence; a
holder can fabricate a consistent manifest and chain. Oracle fixture identities
remain `unverified_fixture`.

The preserved 18-control logs were reaudited into
`GrayBench-v3-admission-control-audit-v5-20260928.json`, SHA-256
`f4f1a8be67e198e4653ba66a5784156c595fecf72b30b3119c82d24fa0bd4e94`.
Twelve controls declare `upstream-proxy-v1`; six declare
`qhe0-size-domain-v1`. None declares a protected public-contract digest, so
`declared_frozen_judge_control_count` is zero. The four covered cards, 298
uncovered cards, and eight upstream false passes remain; there is still no
protected admission evidence in these logs. That historical report remains
local output outside the PR; its input logs are bundled.
The previous report remains preserved. It did not predeclare judge manifests
before execution, so schema 5 also leaves all 18 controls unqualified.

## Predeclared protected controls (report schema 5)

`protected-oracle-review` freezes the source-bound judge manifests in the
header before executing authored controls for the separately revised task-2
and task-20 value contracts. The inspector checks every observed judge digest
and full manifest against that header. The coverage audit requires this
predeclaration in addition to the schema-4 track, contract and exact judge
binding. A runtime change or mismatch leaves an incomplete control log.

On 2026-09-28, the pinned Python 3.12 image
`sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd`
produced six matching controls per task and suite, 24/24 in all. The combined
local JSONL is `GrayBench-v3-protected-controls-both-final-20260928.jsonl`, SHA-256
`321d7cac8b64934f5cc0a5ab7751d8923456453bc9b5d57729dcc4233e8b55d9`.
Each task has three positive alternatives (analytic, Qiskit-derived and global
phase) and three semantically wrong, well-formed values (product state, wrong
basis or fixed layout, and relative minus phase). These are authored, visible
controls, not an unseen holdout or independent review. They demonstrate the
revised numeric value behavior, not the original native-object QHE semantics.

The schema-5 audit combined those 24 controls with the prior 18 into
`GrayBench-v3-admission-control-audit-v7-20260928.json`, SHA-256
`b1e9da8fc9812e796446ccbe2e2cea575e5479ba2975b9db831861fa8f5a8ed9`.
It records 42 controls across 8 cards, 294 uncovered cards and the same eight
upstream false passes. All 24 new controls have predeclared judges. The pending
inventory does not yet bind any card to a protected judge or claim requirement
coverage, so `declared_frozen_judge_control_count` remains zero. This is the
correct admission result; no card or score is published. These evidence files
are in the [committed evidence bundle](artifacts/admission-2026-09-28/README.md).
`admission-bundle-verify` checks recorded hashes and recomputes the audit
against the pinned dataset bytes. The bundle remains unsigned local evidence,
not independent attestation.

## Bound task-2/20 review cards

The [successor bundle](artifacts/admission-bindings-2026-09-28/README.md) keeps
the three original control logs unchanged and binds each normal/hard task-2 and
task-20 card to its revised public contract and exact protected judge. Two
public requirement clauses per card reference authored positive alternatives
and wrong-answer mutants. The recomputed audit has 42 controls across eight
cards; all 24 protected task-2/20 controls now match their card's predeclared
judge and their requirement references have matching local observations.
Eight upstream false passes and 294 cards without controls remain. The bound
inventory digest is
`fe353e883c32319c6816ff084ff69982ccd53646fec83e72dd83e727dac5f57b`;
the audit file SHA-256 is
`618d923a7651d87e9f129bec72a41dae70ca940486676283257d82439f4c2c00`.

The requirement links contain no oracle-fixture digests. Their authored
alternatives do not replace independent reviewers, and the known upstream
findings are still unresolved on the cards. The original pending bundle remains
available as a historical snapshot. Neither inventory is eligible for a
published benchmark score.

## Frozen findings and task 62

The [task-62 native probe](artifacts/task62-fixed-oracle-2026-09-28/README.md)
found another upstream false pass: a fixed circuit ignores the requested BB84
state and basis yet passes the pinned normal and hard tests. An independent
all-zero input gives a different result for the exact canonical function and
that fixed circuit. This is a known oracle limitation, not a score adjustment.

New admission inventories use schema 3 to embed a digest-bound snapshot of the
known-finding registry. Historical schema-2 inventories continue to validate
against their original registry. To carry review work forward, run
`graybench admission-refresh-findings OLD_INVENTORY CACHE NEW_INVENTORY`;
the command validates the old inventory, adds current findings and refuses to
erase historical findings. A separate current-registry check can reject an
otherwise valid historical snapshot when current use is required.

The [successor bundle](artifacts/admission-findings-2026-09-28/README.md)
adds the task-62 finding to both suite cards while preserving the task-2/20
bindings and all 42 prior controls. Its inventory digest is
`a7854800a714a4aed491d02174397910bca5cffde8ae27f258c86f0c7e843ec2`;
the recomputed audit SHA-256 is
`2507b4f75cc6c86a5cc6b5653c8f768f10f4d88571801123a34a1da981e316a4`.
The audit still has 294 cards without controls, no independent reviews and
`publication_eligible: false`.

## Current-source task-62 successor, 2026-09-28

The [current-source successor bundle](artifacts/admission-task62-current-2026-09-28/README.md)
verifies against the pinned normal and hard parquet bytes. Its manifest SHA-256 is
`7ae09096586f140a642601ea7e378a6dc39bf7fe43d3ea7fabb92297c3c24c1c`;
the recomputed audit SHA-256 is
`6f827cbadaf2e26cc844e69d88e450e60442720dc3c89724ab001d9eccb6bd68`.
It has 58 authored candidate controls on ten cards, including 40 linked to
predeclared protected judges. All 40 requirement links have matching local
candidate observations. This does not show that those judges' private fixtures
cover the public requirements.

An inventory-wide count finds requirements and exact public-contract and judge
bindings on only six cards (normal and hard tasks 2, 20, and 62). None of their
requirements cites an oracle-case fixture digest. No card has two review
attestations, and 94 card-level known findings have no resolution evidence.
The other 292 cards have no candidate controls in this bundle. The first three
control logs remain historical earlier-source observations; only the task-62
log binds the current engine source. The bundle therefore remains
`publication_eligible: false` and supplies neither an admitted population nor a
model score.

The later [task-62 case-coverage probe](task62-case-coverage-gap.md) found a
separate false pass in the protected value-v1 case set. That finding is not in
this frozen inventory's registry and has not been resolved. The bundle remains
a historical, verifiable snapshot rather than a current complete-finding
admission claim.

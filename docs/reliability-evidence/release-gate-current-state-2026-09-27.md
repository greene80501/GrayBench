# Current release gates, 2026-09-27

This is a read-only release-path audit of the development engine at analysis
source digest `05438b07b272b0d1ae8af293c8704e886d1ef2e6dd8538b88f162e335108aa0e`.
It does not admit tasks, certify a model, or alter a saved attempt. No provider
request was made.

## What the current code permits

`Ledger.summary` verifies blob hashes, the event chain and row bindings before
reading a run in one SQLite snapshot. It binds the denominator to frozen
task/replicate slots and sets `pass_at_1` only when generations and judgments
are complete, outcomes are scorable, model observations are acceptable, and
the current analysis-source digest equals the frozen digest. Even then it
labels the score `development_only`, sets `certification: not_certified` and
`publication_eligible: false`. `compare_runs` likewise returns either
`unscored` or `development_only` and always sets `publication_eligible: false`.
The current CLI exposes development `summary` and `compare` commands; it has
no publication-admission command. These are observed code gates, not proof
that the underlying oracles are correct.

Importing both pinned suites through `inventory` returned 302 cards. All 302
have pending specification, oracle and wire-interface reviews; none is
release-eligible and `release_ready` is false. Ninety-two cards currently
carry at least one known-finding tag, because a task number appears separately
in normal and hard. Sixteen cards are marked external-service dependent.
The card counts describe the provisional inventory, not completed reviews.

## The current `upstream` recipe is a protected proxy

`recipe_judge("upstream")` constructs `UpstreamJudge`, which starts a trusted
test container and a separate candidate container. `upstream_process.py`
replaces the candidate function with a data-only proxy, removes a pinned
test's top-level `check(...)` invocation and calls `check(proxy)` itself.
Arguments and returns cross the value or graph transport. This is an
intentional trust-boundary design, but it is **not** native same-process Python
execution of the pinned candidate and test. The
[identity-boundary probe](alias-boundary.md) records verdict differences under
value transport, and the
[encoder-integrity probe](protected-worker-encoder-integrity.md) records a
separate false pass under both value and graph transports. Protocol 4's graph
support does not turn this recipe into a native runner.

Consequently the existing `upstream` recipe cannot be promoted into an exact
upstream-native score by renaming it. A native reproduction needs its own
versioned runner and clear disclosure that candidate code can inspect or alter
same-process tests. The protected semantic track needs independently admitted
value contracts and an integrity boundary appropriate to its claims. These
tracks require separate result identities, denominators and release gates.

## Saved provider ledgers under the current engine

The three preserved hosted ledgers have the SHA-256 digests recorded in
[hosted generation conformance](hosted-generation-conformance-2026-09-27.md).
Re-reading them with the current source verified each ledger's internal
integrity. The output was restricted to release fields, without printing
responses or host metadata:

| Run | Current score status | Current score blockers | Publication |
| --- | --- | --- | --- |
| OpenAI `5c4c4af464114a79af683ef55258799e` | `unscored`; `pass_at_1: null` | `analysis_source_mismatch` | Ineligible |
| Gemini 2.5 `85c948d4be03482fade29ff556c09a20` | `unscored`; `pass_at_1: null` | `analysis_source_mismatch`, `missing_generations`, `unjudged_samples` | Ineligible |
| Gemini 3.8 `ed150de3110b434a8ba7fef2886d93ac` | `unscored`; `pass_at_1: null` | `analysis_source_mismatch` | Ineligible |

The analysis mismatch is expected: these attempts froze an earlier engine
source. It is not evidence of ledger corruption. The earlier development
summaries remain historical observations; they cannot be silently recomputed
as current-source scores. Reproduction must use the matching preserved source
and evaluator identities. `ledger_integrity: verified` is internal hash/chain
verification, while the summary still reports `external_anchor: not_checked`.
Provider-returned model names and metadata do not independently attest model
weights or effective sampling settings.

The [request-scope audit](request-scope-provenance-audit.md) additionally
shows that the current transport records the prepared JSON body but not an
observed sent-body digest or non-secret credential/account scope. Two fake
credentials sent different Authorization headers while retaining the same
prepared-request and model-spec digests. This does not invalidate a saved
response by itself; it limits what the present ledger can prove about account
scope and exact cross-track request reuse.

The [HTTP-503 retry audit](http503-retry-ambiguity-audit.md) shows a separate
first-answer risk: the transport marks a 503 as `rejected`, and the frozen
default policy permits replay without evidence that the provider did no
generation. A local mock demonstrates the classification and retry-eligible
status; it is not an observed provider failure. Release-grade retry admission
needs non-acceptance or idempotency evidence beyond the status code.

## Release work still required

The safe default also means this branch has no route to a certified result.
The separately disclosed native and protected tracks need explicit task and
protocol admission, reproducible source/image execution, independent oracle
review, model/settings identity standards, and a release decision that consumes
that evidence. A complete development ledger is not a substitute for those
gates. The current `Adapter.settings` accepts settings marked `documented` or
`verified` for request construction; that is not by itself proof that a provider
honored a setting. Any eventual publication gate must distinguish requested,
documented-supported, observed-effective and unknown controls.

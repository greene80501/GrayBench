# Separate native and protected Qiskit HumanEval tracks

Status: implementation in progress. This document does not admit a task,
change a saved score, or authorize a model campaign.

## Purpose and decision

GrayBench should report two separately named Qiskit HumanEval evaluations,
each with distinct normal and hard results. The user selected both contracts:
native execution to preserve pinned Python/Qiskit test semantics, and a
protected semantic evaluation whose tests remain outside candidate execution.
The system should support Ollama, hosted APIs, and future adapters through the
same immutable generation and reporting pipeline. It should never combine the
two tracks or normal and hard into one accuracy number.

This is the execution-and-scoring architecture slice of the larger
[reliability plan](../../RELIABILITY_PLAN.md). Provider qualification, fresh
holdout authoring, and independent model reproduction remain required release
work, not deferred definitions of success. A finite suite cannot prove universal
correctness or freedom from training exposure; the release claim must name its
frozen tasks, interfaces, threat model, and observed controls.

## Current facts that constrain the design

- The pinned normal and hard files each contain 151 tasks. Eight families in
  each suite need external service access and are outside the currently
  authorized offline scope. A 143-task offline result is an explicitly named
  subset, not a full 151-task QHE score.
- `recipe_judge("upstream")` currently runs tests through a proxy into a
  separate candidate container. It is not same-process native execution. The
  [release-path audit](../../reliability-evidence/release-gate-current-state-2026-09-27.md)
  and [task-50 probe](../../reliability-evidence/task50-110-oracle-review.md)
  show both object-semantics differences and a canonical in-place mutation
  marked `unsupported` by the proxy despite passing natively.
- The current candidate-side value and graph encoders can be substituted by
  candidate code. The [encoder-integrity evidence](../../reliability-evidence/protected-worker-encoder-integrity.md)
  includes a false pass. Protocol 4 graph transport fixes selected alias
  fixtures but cannot attest arbitrary Python objects returned in that process.
- Pinned tests have documented false passes, false rejections, underspecified
  domains, and unstable or service-dependent cases. All 302 current cards have
  pending reviews and `release_eligible: false`; known-finding tags are a work
  queue, not completed admission.
- The upstream project's
  [canonical-solution script](https://github.com/qiskit-community/qiskit-human-eval/blob/c98ba538239fcfd554aa89627ee8026f4b5de450/scripts/test_solutions.py)
  runs trusted reference code with tests in one namespace and explicitly warns
  against using it for network-provided solutions. It does not supply a safe
  model-answer runner. Native GrayBench results must be labeled an adapted
  reproduction unless a published model runner, dataset revision, environment,
  and generation protocol are all matched.

## Track definitions

| Property | Pinned native reproduction | Protected semantic evaluation |
| --- | --- | --- |
| Task source | Exact pinned public prompt and test bytes, with separate normal and hard suite IDs | Separately versioned, public value-based task contract and admitted private oracle |
| Execution | Candidate and pinned test in one isolated Python process, preserving native object identity and in-place effects | Candidate and trusted judge in separate processes/containers; only declared answer values or artifacts cross the boundary |
| What a pass means | The pinned test accepted the answer in the declared runtime and answer-format condition | The frozen semantic oracle accepted the declared value contract on admitted valid inputs |
| What a pass does not mean | The candidate cannot inspect or alter tests; the pinned test proves the public requirement | An arbitrary native Qiskit object, Python class identity, method call, or in-process side effect was attested |
| Task admission | Every scheduled task must pass reference, environment, flake, and execution-shape preflight; known oracle limits remain disclosed | Every scheduled task needs a reviewed public contract, independent correct alternatives, deliberately wrong controls, wire/value fidelity tests, and a release decision |

The new track IDs are `qhe-pinned-native-v1` and
`graybench-protected-semantic-v1`; suite and release IDs further distinguish
normal, hard, and eligible subsets. The existing `upstream`, graph, and named
revision recipes retain their historical identities. They remain development
evidence and are not renamed into either new headline track. Robustness,
prompt-format, resource, and tool-assisted studies have their own condition
IDs and tables, never a third component of a combined headline score.

## Frozen experiment and data flow

1. A release manifest declares track ID, suite, exact expected task IDs,
   dataset/task revision, eligible set and exclusions, public prompt and
   response contract, extraction rule, runtime/image digest, limits, judge
   digest, metric code, retry policy, model endpoint and capability evidence.
   It is approved and content-addressed before generation. A release cannot
   choose eligibility by keeping only tasks whose reference happened to pass.
2. An adapter renders the exact request for each public task. It may use a
   model's documented native endpoint and chat template, but the information
   content, number of answers, resources, tools, and assistance policy are
   disclosed and comparable within the reported condition. No test, reference
   answer, task-specific hint, retrieved solution, or repair feedback enters
   the request. Normal retains its public imports/function prefix; hard does
   not receive replacement imports. Literal continuation and chat-oriented
   full-function formats, if both used, have distinct frozen condition IDs.
3. The generation ledger retains every scheduled task/replicate, the exact
   content-bearing request bytes sent to the endpoint (path, body, and
   content-affecting headers; credential-bearing header values are excluded
   and the account/credential scope is identified without the secret), dispatch
   event, transport attempts, returned text, provider IDs, finish reason,
   token accounting, metadata observations, and hashes before judging. The
   adapter also stores a canonical prepared-request digest. If an SDK hides
   transmitted request bytes, that generation is ineligible for headline
   cross-track reuse until the adapter can attest them. A returned empty,
   malformed, refused, or truncated first answer is not regenerated.
   A transport retry is allowed only under a predeclared rule that proves no
   prior accepted generation; ambiguous delivery stops for adjudication.
4. The same generation may contribute to both headline tracks only when the
   exact request and response bytes, model/configuration identity, public
   task contract, and extraction policy match and both judgments were
   scheduled before dispatch. Each judgment has its own track, task release,
   runner, oracle, and outcome identity. A later immutable exploratory
   judgment may be added, but it cannot replace a preregistered headline
   result.
5. Reporting reads a verified ledger snapshot and release manifest. It emits
   normal and hard tables per track, the exact denominator and task IDs,
   per-task outcomes, exclusions, error counts, requested versus observed
   settings, model identity limits, uncertainty, and reproduction commands.
   It rejects cross-track pooling and comparisons with mismatched dataset,
   request, extraction, runtime, or judge identities.

## Native runner boundary and limits

The native worker executes the frozen candidate assembly and pinned test in
one Python interpreter inside an immutable Python 3.12/Qiskit image. The
candidate/test container has no network, credentials, host user files, or
Docker socket; it uses a non-root user, read-only image, bounded temporary
storage, CPU/memory/process limits, deadline, and output cap. A separate host
supervisor records container status and artifacts. The execution plan freezes
how normal tests without a top-level `check` call and hard tests with one such
call are invoked exactly once; it must reject an unexpected test shape rather
than silently rewriting it. Candidate source and test bytes stay in the
recorded artifact identity.

Same-process execution deliberately exposes test frames and imports to a
malicious candidate. The supervisor must treat early exit, missing completed
check evidence, forged text markers, and abnormal termination as non-passes,
with adversarial fixtures. It cannot prove that a determined candidate did
not tamper with its same-process test. Native results are therefore a pinned
test reproduction with a disclosed integrity limit, not a hidden-test or
cheat-resistant certification. Exact equivalence to a named published score
requires a separate compatibility record for runner, dataset, prompts, model,
decoding, runtime, and denominator.

## Protected semantic boundary and task admission

The protected track measures only what its public value contract states. A
candidate may emit a scalar, array, circuit representation, file, or other
bounded value when the task version explicitly defines it. The trusted judge
parses and reconstructs that representation, checks allowed input and output
domains, then evaluates semantic properties. Fabricating a valid representation
is an acceptable answer to a value task; it is not evidence that a native
Qiskit class was constructed or a named internal method was called. Tasks
whose real requirement is native identity, aliasing, mutation, or unobservable
method use are revised with a clear new public contract or held ineligible.
The task-50 mutation and task-126 fixed-fidelity cases illustrate both limits.

The candidate never receives private tests, oracle expected values, judge
credentials, or a writeable verdict channel. Candidate-controlled serialization
is never treated as proof of native-object provenance. Each wire type has
bounds, a versioned decoder, round-trip and adversarial controls, and an
explicit unsupported result. A candidate timeout or format error may count
as a failed first answer under calibrated frozen limits; unsupported
interfaces and judge infrastructure errors block a score rather than being
silently removed from the denominator.

Each normal/hard task card records public requirements, input domain, return
representation, side effects, dependencies, randomness, resource limits,
oracle assertions, expected correct alternatives, and wrong mutants. A
requirement is scored only when its valid domain and oracle can be defended.
Two independent Qiskit-competent reviewers resolve material ambiguity without
seeing model labels or aggregate standings. New or repaired tests are frozen
as a new release before candidate generation; upstream bytes and earlier
judgments remain available unchanged. An unadmitted or externally dependent
task is listed with a reason and cannot enter the protected score.

## Score and publication gate

For each track and suite, a release declares its task IDs before any scored
generation. `pass@1` uses the first returned answer in every scheduled cell;
additional repeats estimate uncertainty but do not allow answer selection.
Passing, candidate error, and calibrated candidate timeout are distinct
reported outcomes. An unresolved delivery, unsupported value contract,
infrastructure error, unexplained reference failure, flaky oracle, missing
generation/judgment, or changed source identity leaves the run unscored or
development-only. Offline 143-task and admitted protected subsets carry their
own names and task lists. A full 151-task label is unavailable until service
cases are actually qualified and run under a frozen, authorized condition.

Publication requires complete scheduled evidence, model/setting capability
records, independent task and result review, external anchoring or signed
release evidence outside the execution worker, and a clean-machine replay of
verdicts and tables from pinned source and images. Provider-reported names do
not verify proprietary weights. Unknown or ignored sampling controls must be
reported as such; a run cannot be called greedy from a requested temperature
alone. Published IBM, ScienceEval, and paper numbers remain contextual until
all relevant artifacts and conditions are matched.

## Verification and migration criteria

- Verify native assembly against pinned normal and hard reference controls,
  including in-place mutation, aliasing, early exit, forged result markers,
  exception, timeout, and test-shape cases. A mismatch receives an explicit
  diagnosis; it is never patched by special-casing a model answer.
- Verify protected task values with correct independent implementations,
  deliberately wrong mutants, boundary inputs, encoder-substitution fixtures,
  resource ceilings, and repeated executions. The known false pass must cease
  to be a false pass under an admitted value contract, or the task remains
  ineligible.
- Freeze request rendering and extraction before comparing Ollama and API
  models. Check endpoint metadata, effective-setting evidence, ambiguous
  transport, resume, and response preservation without leaking credentials.
- Exercise complete scheduled normal and hard cohorts locally in the pinned
  environment, then reproduce the release bundle on a clean second machine.
  CI may later provide another check but is not release evidence while the
  repository workflows are disabled by GitHub billing.
- Preserve all historical V2/V3 ledgers and current development recipe IDs.
  New track IDs and schema migrations must not reinterpret old judgments.
  A release gate is added only after its manifest validator and negative
  controls reject incomplete or contradictory claims.

Implementation is split into reviewable increments under this design. The
first plan covers track identities, manifest and ledger binding, native runner
parity, and its local verification controls. A later plan covers protected
value-contract admission and the report/release boundary; broader oracle
authoring, provider qualification, and campaign execution follow. No
increment can publish a headline score before the full release gate passes.

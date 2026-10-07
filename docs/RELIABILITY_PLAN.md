# GrayBench reliability and fairness overhaul plan

GrayBench should become an auditable measurement system whose task definitions, judge, model interfaces, sampling policy and published claims can each withstand independent verification. The existing overhaul is a useful baseline, but it is not sufficient evidence of a fair or trustworthy final leaderboard. Python 3.12 is one reproducibility component, not the definition of success.

The recommended next release has three separately reported evaluations: upstream replication, strengthened correctness, and robustness under controlled changes. Its primary practical question is: **How reliably does a model produce a correct first answer for a clearly specified Qiskit task in a declared environment, without task-specific assistance?** No finite test suite can prove universal correctness or complete absence of training contamination. The achievable standard is an explicit threat model, strong falsification tests, controlled comparisons, reproducible evidence and bounded claims.

## 1. Findings that change the plan

These findings were checked against current code, pinned datasets and isolated Docker execution. They are observed results, not just hypothetical risks.

| Finding | Evidence | Consequence |
|---|---|---|
| The judge accepts a fabricated success message | A synthetic wrong function printed the expected result marker and exited before assertions ran; the evaluator returned pass. The correct control passed and an ordinary wrong control failed. | Judge integrity is a P0 release blocker. Container isolation does not establish verdict integrity. |
| An official test accepts a plausible incorrect solution | Pinned normal task 20 accepted a transpiled empty circuit with the requested layout, although the prompt requires a GHZ circuit. | Every task needs semantic requirements mapped to tests and deliberately wrong implementations. |
| Test breadth has not been established | In each 151-task suite, 127 tests have one syntactic candidate call and 34 have at most one assertion. | These are review priorities, not proof that all those tests are inadequate. Loops and rich assertions can test more than these counts suggest. |
| Requested settings are not proven effective settings | Pilot Gemini requests contain temperature 0 and top-p 1. Current Google guidance advises removing sampling overrides, and Firebase documentation describes ignored sampling controls. | Distinguish requested, supported, documented-effective and unknown settings. The pilot is not a verified greedy-decoding experiment. |
| The environment-disclosed experiment confounds two changes | It adds both runtime versions and a code-only instruction, after observing baseline failures. | Preserve it as exploratory; separate the factors in a preregistered study. |
| A Google result required operational recovery | Normal run 897c688f is invalid after a 504; its reported composite uses 142 original answers and task 103 from recovery cc783a0c. | Recovery needs a first-class, predetermined policy, not a manual reporting exception. |
| Current uncertainty estimates are limited | Wilson intervals exist, but repeated-generation estimates and paired model comparisons do not. | Small differences and rank claims are not established. |
| Source attribution was misconfigured | Branch commits used a placeholder email. The repository now uses a GitHub-linked address; the approved squash merge is attributed to greene80501. | Future changes must use the corrected identity and verified GitHub attribution. |

The evidence files are `GrayBench-judge-integrity-probe.json`, `GrayBench-task20-oracle-probe.json` and `GrayBench-test-inventory.json`. A literal scan of 1,002 stored pilot attempt records found none of five specific tampering markers, including the forged-result marker and early-exit pattern. That is not a comprehensive tamper audit or correctness proof, but provides no evidence that the tested models used the demonstrated bypass. See `GrayBench-pilot-integrity-scan.json`.

Google documentation has evolved: older Gemini 3 guidance recommends temperature 1.0, replacement guidance recommends omitting sampling overrides, and newer documentation describes ignored parameters. The Gemini 3.6 model page establishes model identity and limits but not effective sampling for the historical requests. The finding is a provenance gap, not proof of the direction or magnitude of score bias. [Google migration guidance](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5), [Firebase parameter guidance](https://firebase.google.com/docs/ai-logic/model-parameters), [Gemini 3.6 model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash).

## 2. Define fairness before seeing scores

The same nominal temperature, token count or serialization is not necessarily an equivalent opportunity: tokenizers differ, endpoints support different controls, and chat models have native interface conventions. Conversely, tuning a special prompt until each model performs best measures model-plus-optimization rather than controlled first-answer capability.

| Dimension | Required rule |
|---|---|
| Information | Same task requirements, public context, runtime target and allowed resources within a comparison. No answers, hidden assertions, task-specific hints or feedback in generation requests. |
| Interface | Documented native interface for each model, preserving the same semantic content. Archive rendered requests and template versions. |
| Opportunity | Same number of returned answers per task and repeat. No regeneration for wrong, empty, refused or truncated returned answers. |
| Resources | Explicit generation and execution limits. Report capability, cost and latency separately; equal token counts are not equal compute. |
| Judgment | Same frozen test release, oracle, tolerances and task eligibility for every model. |
| Reporting | Preserve every scheduled run and deviation. No best-run selection, silent exclusion or ranking across incompatible tracks. |
| Governance | Do not optimize protocol decisions for a favored model's score. Adjudicate defects with model identity hidden where feasible. |

HELM supports controlled adaptation, multiple metrics and explicit coverage limitations. Prompt-format research shows that meaning-preserving presentation changes can affect models differently. Together they support measuring sensitivity rather than declaring one arbitrary format universally neutral. The reported effects in that research are not estimates of GrayBench's own sensitivity. [HELM](https://crfm.stanford.edu/2022/11/17/helm.html), [Sclar et al., ICLR 2024](https://arxiv.org/abs/2310.11324).

## 3. Keep three evaluation tracks distinct

**A — Upstream replication.** Preserve the exact upstream task revision, prompts and tests. Match a published runner, runtime and generation configuration where available. If anything is unavailable or changed, label the result an adapted reproduction and list differences. The 143-task offline subset must never be labeled the complete official 151-task score. Normal intentionally supplies imports and a function prefix; hard intentionally does not. Removing that normal context or adding missing imports to hard would change the task. [Official QHE repository](https://github.com/qiskit-community/qiskit-human-eval).

**B — Strengthened correctness, recommended primary track.** Create a separately versioned GrayBench Verified task release. Repair ambiguous specifications and inadequate tests through documented changes. State runtime and output contract uniformly, but supply no examples, solution hints, replacement imports, hidden tests, retrieval or repair turns. Declaring the target environment avoids an unnecessary guessing game; it does not supply the solution. This changes the upstream protocol and therefore needs its own name and score. Hard continues to omit the normal implementation prefix.

**C — Robustness and resource sensitivity.** Use a frozen matrix of equivalent prompt formats, supported runtime versions, generation budgets and repeated requests. Report all planned conditions and ranking stability. Documentation-assisted, tool-using, agentic and iterative-repair systems belong in additional labeled conditions, never in the first-answer table.

Do not combine these tracks into one overall leaderboard. Normal and hard are related information conditions and share task families; they are not twice as many independent programming problems.

## 4. Audit specifications before strengthening tests

Create a task card for every normal/hard pair, including the eight service-dependent tasks. Record identity and ancestry, accepted input domain, return contract, side effects, semantic requirements, runtime compatibility, randomness, resource expectations, external dependencies and ambiguous language. Distinguish mandatory implementation techniques from techniques merely used by the canonical answer.

The [full 151-family contract review queue](reliability-evidence/qhe-full-contract-review-queue-2026-10-07.md)
now records public behavioral obligations, unresolved choices/process requirements
and proposed falsification controls for every pinned family. It is a source-bound
authored draft, not completed task cards, observed mutant results or independent
admission. Its coverage includes the service-dependent families and preserves
normal/hard ancestry. Turn every proposed scored clause into reviewed case and
control evidence before release.

Map every scored requirement to a test and to a deliberately wrong implementation that should fail. A correct reference passing is necessary but insufficient. Add an independently implemented correct alternative where feasible, so the judge does not reward only the reference's style. Two Qiskit-competent reviewers should resolve ambiguous cases without model labels or aggregate standings. LLMs may propose cases, but their agreement or generated reference is not the final authority.

The 151-task inventory is a full review obligation. Eligibility must not become whatever happened to pass preflight. Declare expected task IDs before preflight; an unexpected reference failure blocks that release for investigation. Distinguish defective tasks, unsupported runtimes, missing infrastructure and service dependence. Publish every exclusion and its rationale.

Task 9 illustrates the importance of version identity: an upstream issue documented missing barrier verification and a check against the wrong object. That issue is closed, and the pinned local task includes barrier checks. It would be incorrect to cite the historical issue as an unfixed local defect. The task 20 probe, by contrast, tests the current pinned version. [Upstream issue 23](https://github.com/qiskit-community/qiskit-human-eval/issues/23).

Document dataset purpose, construction, intended use and maintenance, following the rationale of Datasheets for Datasets. [Gebru et al.](https://arxiv.org/abs/1803.09010).

## 5. Strengthen correctness oracles

Use property-based tests, independently derived expected results, metamorphic checks and mutation testing. Generate only inputs allowed by the published contract: testing unspecified behavior unfairly broadens the task after generation. EvalPlus shows that stronger tests can expose false passes and alter rankings; it also emphasizes valid-input contracts. This supports the method, not an assumed Qiskit score change. [EvalPlus](https://arxiv.org/html/2305.01210v3).

| Task kind | Required checks and wrong controls |
|---|---|
| State preparation | Compare amplitudes or density matrices under the specified phase convention; verify entanglement/correlations when required. Reject product-state substitutes for GHZ or Bell states. |
| Unitary construction | Compare operators with declared tolerances. Allow global phase only where the contract permits it; phase behavior can change when an operation becomes controlled. |
| Transpilation/layout | Check logical behavior after accounting for layout, allowed gates, connectivity and mapping. Reject a correctly mapped circuit implementing the wrong computation. |
| Measurement/sampling | Verify distributions, bit ordering and register mapping under a prespecified statistical test. Control seeds where possible and quantify false rejections. |
| Classical values | Check promised types, shapes, values, ranges and permitted edge cases. Do not confuse a canonical representation with semantic correctness. |
| Circuit structure | Check explicitly required operations, counts and parameters; allow equivalent decompositions where the prompt permits them. |
| Plots/files | Check promised artifacts and relevant content; do not depend on display availability or incidental styling unless specified. |
| External services | Use a separately labeled authorized integration track. An offline emulator is a different benchmark, not proof of real service success. |

Use bounded small circuits for exact oracles. Large-state simulation has exponential cost; some tasks require structural invariants or other bounded checks. Quantum metamorphic testing provides useful transformations with known relationships, but those relationships must fit unitary, non-unitary or noisy behavior as applicable. [MorphQ, ICSE 2023](https://arxiv.org/abs/2206.01111).

The mutation catalog should remove entanglement, swap control/target, reverse endianness, change rotation signs, ignore arguments, omit required barriers, return fixed examples, produce the right shape with wrong values, and use obsolete APIs. Exclude equivalent mutants only with justification. Do not inflate mutation scores with trivial import failures.

**Proposed gate:** every critical requirement has a reviewed counterexample rejected by the judge; every correct alternative passes; zero unexplained surviving critical mutants; at least 95% of reviewed non-equivalent mutants rejected overall, with per-task results and all survivors disclosed. The 95% threshold is an engineering proposal, not a universal standard or correctness proof. Requirements about how a computation was performed cannot always be established from output behavior; clarify, redesign or separately review them rather than pretending they are verified.

## 6. Replace the verdict trust boundary

Candidate code and tests currently share a Python process, and the host accepts a recognizable stdout line. Separate dictionaries do not separate privileges or protect Python state. A random marker or hidden filename is inadequate if candidate code can read or modify the judge's state.

The replacement bridge also needs an explicit worker-integrity gate: candidate
code currently executes in the same process as the candidate-side value encoder.
In a local task-2 repro, patching `Statevector.data` and `dims` caused the old
encoder to transmit a different state and subsystem shape than the exact
object stored. Raw-field validation closes those two accessor paths, but
candidate code could still patch the encoder itself. A trusted oracle can
verify the reconstructed wire value; it cannot infer an unmodified candidate
object or construction procedure from a candidate-controlled serialization.
Keep affected recipes release-ineligible until this boundary is adjudicated
with adversarial protected controls. The
[local worker encoder probe](reliability-evidence/worker-encoder-integrity.md)
reproduces a false pass for a returned task-2 object without Docker; it is a
boundary finding, not a model score or proof of protected execution.

Use a trusted orchestrator and oracle outside the candidate sandbox. The candidate receives the task and individual input values, never expected answers or future checks. Its stdout is diagnostic data, not a verdict channel. It returns bounded data; the trusted side validates that data, computes correctness and records completion itself.

Qiskit complicates this design. Define typed return schemas for circuits, layouts, operators, arrays and artifacts. Never unpickle candidate-controlled objects in a trusted process, and do not assume arbitrary object serialization or QPY parsing is a safe boundary. Validate sizes, nesting, finiteness, identifiers and formats before constructing trusted objects. Constrain and test parsers separately.

The representation must preserve parameters, phase, classical registers, layout and every other contract-relevant property. A candidate claim that its output is correct is not evidence. Arbitrary callbacks, object identity and stateful contracts may not fit a strong boundary initially; label them unsupported for certification until the design is validated. Do not silently fall back to the old judge. Conversion changes need a documented compatibility analysis and correct-alternative tests.

Probe forged verdicts, early exit, monkeypatching, test-file access, stack inspection, environment access, malicious serialization, child processes, output floods, memory exhaustion and timeouts. Positive controls must show ordinary correct code still works.

**Gate:** the known bypass fails; the critical adversarial suite has zero false passes; candidate code cannot author trusted success; trusted completion evidence exists for expected checks. This is assurance within a stated threat model, not immunity to every interpreter or kernel exploit.

## 7. Make provider behavior explicit

Introduce a versioned capability record for each exact model and endpoint: supported roles, generation mode, native template, sampling and reasoning controls, output/combined token limits, seeds, finish reasons, refusal signals and usage fields. Preserve exact requested and served model IDs, timestamps, SDK versions and documentation links with dates.

The ledger must distinguish intent, serialized request, provider response and effective settings where verifiable. Ignored controls must be recorded as ignored; unexposed behavior remains unknown. Mock adapter tests cannot prove a hosted service honored an option. Use small non-benchmark contract probes and official documentation. Model-list membership alone does not prove generation access.

The opt-in [protocol 3.2 attempt-observation revision](reliability-evidence/attempt-model-observation-v32.md)
binds provider-reported metadata before and after each transport attempt and
retains returned answers when the post-check fails. This closes a ledger gap,
not the stronger release requirement to attest the model and effective settings
throughout an opaque hosted request.
The opt-in [protocol 3.3 timing revision](reliability-evidence/model-observation-timing-v33.md)
freezes maximum pre-observation age and post-delivery delay and blocks a score
when those bounds fail. Its host-clock measurements still require independent
attestation for release provenance.

Native templates and required defaults can vary, but semantic information and assistance cannot. Prohibit hidden few-shot examples, task-specific system prompts, answer repair and content-dependent endpoint switching. Models available only through agents or Responses-style interfaces need proper adapters and declared profiles, not forced use of an incompatible endpoint followed by a poor score.

The lm-evaluation-harness interface makes chat templates, generation configuration and sample logging explicit. Borrow those accounting principles; adopting a framework does not automatically establish fairness. [EleutherAI documentation](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md).

## 8. Separate capability limits from cost comparisons

The primary capability profile should allow one returned answer per task with a generous allowance established on development tasks before release evaluation. Tokenizers and hidden reasoning accounting prevent a universal equal-compute claim. Provider-native defaults are a defensible interface policy, but not proof of equal inference compute.

Use a development budget ladder, for example 16k, 32k and 64k where supported. Define adequacy using finish reasons and truncation on disjoint development tasks, then freeze the profile for every release task. A model unable to support it receives a disclosed constraint or different comparison group. Never increase the allowance only for failed tasks or choose each model's best post-hoc condition.

Publish separate accuracy-versus-cost and accuracy-versus-latency curves under prespecified budgets. Record output and reasoning tokens where exposed, total tokens, finish reasons and latency. Cost reflects pricing, not only computation; tokens are not FLOPs. The pilot's 16,384 cap is a recorded choice, not proof that every model had enough room.

## 9. Freeze prompts and extraction rules

For the strengthened track, disclose runtime and response contract equally. Test version disclosure and code-format instructions as separate factors, not one combined intervention. Neither should be introduced only after one model's failures. Use a small preregistered set of equivalent renderings to quantify sensitivity rather than finding the best rendering per model.

For completion tasks, specify when a body is appended to the public prefix. For standalone tasks, specify permitted packaging. Multiple blocks, duplicate definitions, surrounding prose, empty responses, refusals, partial code and malformed fences need a deterministic policy independent of tests and model identity. If multiple alternatives appear, reject ambiguity or use a fixed disclosed rule; never try alternatives and keep whichever passes.

Maintain correct and incorrect representation fixtures covering varied output styles. Check that normalization preserves semantics. Report formatting failures separately while retaining them in the specified first-answer denominator. A stricter parser is not automatically fairer; a more permissive parser is not automatically better.

## 10. Control runtime drift and flaky judgments

Keep Python 3.12 and one pinned primary Qiskit environment. Pin container digest, dependencies, backend fixtures, relevant compiler/BLAS details, threads, locale, simulator/transpiler seeds and execution resources. Legacy-runtime comparisons are separate conditions. Do not choose the best runtime per model.

Before release, replay all references and independently correct alternatives across fresh containers and at least two clean machines. Begin with 20 replays per deterministic reference and a larger campaign for stochastic checks. Zero failures in 20 runs is only screening evidence, not a sub-1% failure guarantee. Under genuinely independent Bernoulli trials, about 299 zero-failure trials are needed for a one-sided 95% upper bound below 1%; independence and multiplicity still require examination.

Calibrate time and memory limits on independently constructed correct implementations, not only the fastest reference. Separate startup/infrastructure failure from candidate execution. Resource-limit failures remain labeled outcomes. Run reference sentinels before and after campaigns; quarantine batches when infrastructure invalidates judging.

Recent Qiskit-specific preprints support treating version validity separately. Bugs4Q revalidation found benchmark labels could become invalid across runtimes; a separate API-drift study measures requested-version fidelity. These are supporting preprints, not established replication standards. [Brahmbhatt et al., July 2026](https://arxiv.org/abs/2607.09007), [Rasyidi and Faiz, July 2026](https://arxiv.org/abs/2607.04072).

## 11. Replace manual recovery with an immutable ledger

Separate scheduled sample, transport attempt, returned generation and evaluation. Identify a sample by task, model, profile and repeat. Retries are visible child transport attempts. Preserve provider request IDs, timing, errors, partial responses, usage and selection policy. Unknown billing remains unknown.

Before launch, freeze a delivery policy for every model. New native and protected runs use one dispatch per sample; the builders for legacy development tracks do the same, but those older tracks can still be explicitly instantiated under their earlier retry conditions and cannot become either new track's headline result. Authentication, billing, rate-limit and unsupported-model failures leave the sample operationally incomplete under the new policy. A 5xx response, timeout, or interrupted stream cannot prove that the service did no generation; mark it ambiguous and never silently replay it. Any future retry-capable release condition needs endpoint-specific non-acceptance or idempotency evidence, an explicit frozen policy, and its own comparability label. Historical development protocols retain their earlier retry fields and identities. Returned empty, refused, truncated or wrong answers consume the sample and cannot be retried for improvement.

Separate capability from operational reliability. Publish completion coverage and error rates for each model. An incomplete campaign cannot silently drop unanswered tasks, turn them into incorrect code, or appear complete. Diagnostic bounds can be shown, but definitive comparison waits for the planned sample set under its policy. Retries may correlate with difficult requests; measure and disclose that limitation.

The Gemini task-103 composite remains a pilot. New release results must follow a predetermined policy; the manual composite cannot retrospectively become preregistered.

## 12. Use statistics suited to the claims

The primary metric is task-averaged first-answer success under a specified generation policy. Plan repeated independent generations for every task, not extra attempts after failures. Use a separate three-repeat development study; ten repeats per task is a proposed publication starting point, subject to a power analysis and precision objective settled before launch.

With multiple samples, estimate pass@1 from the average success proportion per task. Pass@k is a separate multiple-candidate opportunity metric, requiring enough samples. It cannot replace first-answer reliability. HumanEval uses the estimator `1 - C(n-c,k)/C(n,k)` for each task. [Original implementation](https://github.com/openai/human-eval/blob/master/human_eval/evaluation.py).

Compare models on matched tasks. Use paired task/family bootstrap intervals for differences; use exact McNemar testing only where a single paired binary observation and its assumptions fit. Cluster repeated generations and normal/hard variants at the shared task/family level. Predeclare primary comparisons; use a correction such as Holm for exploratory multiple comparisons. Publish effect sizes and intervals, not only p-values. [Dror et al., ACL 2018](https://aclanthology.org/P18-1128/).

Distinguish generation variability on this fixed set from uncertainty about broader programming tasks. For orientation, 143 independent tasks near 50% accuracy imply roughly an eight-percentage-point 95% margin. An illustrative three-point margin requires about 1,068 independent tasks at worst-case variance. Repeating the same tasks does not create more independent task types, and dependence can make these approximations optimistic.

Report micro scores and prespecified topic/family breakdowns. Freeze any macro weighting. Describe close rankings as unresolved when evidence does not separate them. A difference is not causal evidence of superiority when prompts, budgets, dates or environments differ.

## 13. Reduce contamination and evaluator overfitting

Treat current public QHE tasks and inspected pilot outputs as development or historical evaluation material for the next version. They remain useful regression fixtures, but cannot be an untouched holdout after development against them.

Create fresh, independently authored Qiskit tasks with documented dates, licenses and family separation from development data. Keep expected outputs and test seeds unavailable to generation prompts, tool access and evaluator tuning. Version public development and controlled evaluation splits separately. Commit or hash the held-out artifact before submissions; restrict access and retain an audit trail. Sending it to model services during development would compromise a later claim of non-exposure.

Use near-duplicate and structural-similarity analysis, not only string matching. Dates and model cutoff claims mitigate some risks without proving non-exposure for opaque models. LiveCodeBench's time-segmented design is useful precedent; a frozen historical release is not automatically fresh for a current model. [LiveCodeBench paper](https://arxiv.org/abs/2403.07974), [project](https://livecodebench.github.io/).

Balance security with reproducibility through controlled independent review, public protocols, appropriately disclosed per-task evidence and release of retired holdouts. Secret tests alone do not establish quality or transparency.

## 14. Compare published results through compatibility records

For every external result, record exact model/checkpoint, dataset revision and count, task IDs, prompt/template, sample count, decoding, reasoning and output limits, runtime, parser, tests, retries, tools, date and metric. Missing fields are unknown. Classify comparisons as exact replication, matched subset, adapted reproduction or contextual reference.

| Reference | What it provides | What it does not establish |
|---|---|---|
| Original QHE paper | Motivation and a historical protocol | Equivalence to today's expanded dataset or SDK |
| IBM Code Assistant table | Official Qiskit-specialized normal/hard results and model-specific prompts | Identical prompts or complete runtime identity for GrayBench |
| ScienceEval | Published QHE results for o3 High and Gemini 2.5 Pro | Identical questions, or comparability to Gemini 3.6 |
| EvalPlus | Evidence that stronger tests expose wrong code and can alter rankings | An expected numerical score drop for QHE |
| LiveCodeBench | Time-segmented coding evaluation | Same domain or a contamination guarantee for QHE |

IBM lists Qwen2.5-Coder-14B-Qiskit at 49.01% normal and 25.17% hard, and explicitly says models use their respective system prompts. ScienceEval lists o3 High at 47.02% and Gemini 2.5 Pro at 52.98% for QHE. These remain contextual until data and configurations align. The earlier local comparison found changed prompts and tests under reused ScienceEval task IDs. Similar percentages would not validate GrayBench; different percentages would not alone invalidate it. [IBM table](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-code-assistant), [ScienceEval](https://github.com/ScienceOne-AI/ScienceEval), [QHE paper](https://arxiv.org/abs/2406.14712).

Select at least one available, fully specified checkpoint with public reference artifacts for a meaningful reproduction. If an API snapshot is unavailable, disclose that rather than substituting a newer model. Outreach requesting missing author artifacts would require separately authorized communication.

## 15. Version the experiment, not just execution code

Create immutable identities for dataset, generation specification, judge specification and comparison/analysis specification. The current evaluator hash covers preflight and execution files. Scientific comparability also depends on provider behavior, extraction policy, sample selection and metric code. Store the full source commit and all relevant configuration hashes.

Archive responses before scoring. Every rescoring is a new judgment of the same generation, never a replacement of originals. Content hashes detect accidental modification; a manifest that can be rewritten and rehashed is not an authenticity guarantee. Use protected immutable storage and signed releases, with signing authority outside the untrusted runner.

A release bundle needs the protocol, task cards or controlled holdout metadata, commit, lockfiles, image digest, schedule, permitted requests/responses, selected-attempt provenance, verdict evidence, error ledger, exclusions, per-task metrics, uncertainty analysis and exact reproduction commands. A schema validator must reject contradictory manifests and incompatible comparisons.

## 16. Implementation order and measurable gates

These are proposed work packages, not claims of existing functionality. Estimates are engineering effort, excluding API queues, independent expert availability and extensive fresh dataset authoring. Quality gates take priority over calendar targets.

| Phase | Work and proposed artifacts | Acceptance gate | Estimate |
|---|---|---|---|
| 0 — qualify baseline | Mark pilots; publish defects; freeze v2 evidence | No certified-fair leaderboard claim; all original artifacts preserved | 0.5–1 day |
| 1 — protocol | `protocol/v3.yaml`, task-card and capability schemas, preregistration, expected eligibility | Reviewers can determine assistance, budgets, outcomes and exclusions before generation; critical policy choices resolved | 2–4 days |
| 2 — judge integrity | Trusted oracle/worker boundary, typed schemas, bounded decoding, adversarial fixtures | Known bypass rejected; critical threat suite passes; supported return semantics preserved | 3–6 days, potentially longer for complex objects |
| 3 — oracle audit | 151 paired task cards, requirement maps, correct alternatives, mutation catalog, versioned errata | Every scored requirement verified; zero unexplained critical survivors; all correct controls pass | 5–10 days plus review |
| 4 — provider and ledger | Capability profiles, contract probes, immutable sample/transport ledger, deterministic resume | No duplicate logical samples or hidden retries; ignored/unsupported settings explicit; costs known or labeled unknown | 3–5 days |
| 5 — calibration | Development-only prompt/budget study, runtime replays, resource calibration, fresh holdout design | Frozen settings; no unresolved flakes; no holdout exposure to tuning | 3–5 days plus task authoring |
| 6 — reproduction | Paired metrics, clustered uncertainty, compatibility checks, signed bundle | A second implementation/clean machine reproduces verdicts and tables; unexplained differences block publication | 2–4 days |
| 7 — campaign | All scheduled model/task/repeat cells, predefined recovery and independent review | Full planned evidence, no hidden selection, final provenance/leakage checks pass | Campaign-dependent |

The dependency order is protocol, judge/task/provider assurance, calibration, frozen release, campaign, then independent publication review. Task-card preparation and provider inventory can proceed while the judge is designed, but no final model campaign should precede those gates. A reasonable planning allowance is several weeks; judge complexity and expert task review determine the real schedule.

Assign a maintainer to implementation, a Qiskit reviewer to task contracts and oracles, and a separate reviewer to reproduction and adjudication. The same model or person generating the answers should not be the only judge of their correctness. Additional reviewers are a resource requirement, not an assumption that they have already reviewed anything.

For each implementation PR, include the concrete defect, source/protocol change, regression or controlled experiment, before/after task-level evidence, compatibility implications and the gate it satisfies. Do not hide multiple protocol changes behind an improved aggregate score. Where a change alters measurement, bump the relevant version and replay all eligible stored outputs uniformly.

The development budget study should initially use only currently authorized OpenAI and Google access. DeepSeek, Moonshot, Anthropic and IBM Quantum setup remain excluded. Full external-service evaluation is a separate future scope; any offline simulator must be labeled as a different condition.

## 17. Treatment of existing measurements and GitHub work

Preserve existing measurements as **v2 pilot results under the documented evaluator**. Do not silently alter scores in response to this audit. The probes do not prove every pilot answer is wrong, and no model generation was used in them.

After repairing judge integrity, replay every stored answer and publish a per-task verdict diff. After strengthening semantic tests, replay again as a separately versioned correctness experiment. Neither is untouched replication: current public tasks and outputs have influenced development. Fresh preregistered generation on the finalized release and holdout is needed for publication-quality ranking.

The approved baseline PR is merged as `17ea7fdd90b83c214da9e38bad5648575db760e8`. GitHub confirms author Wyatt Greene, account `greene80501`, with its linked noreply address. GitHub is the merge committer, as expected for its merge workflow. Future implementation should use new branches and this corrected author identity, with focused PRs and gate evidence. No new production benchmark implementation is claimed by this plan.

## 18. Definition of a release ready for serious comparison

A release is ready only when its capability and information conditions are explicit; every included task has an audited contract and strong positive/negative controls; candidate code cannot author trusted verdicts; provider behavior is documented; coverage, budgets, sampling and recovery were fixed before evaluation; stochasticity and runtime instability have been measured; fresh and tuning data are separated; all scheduled outcomes are preserved; statistical and configuration limits are respected; and a separate reviewer can reproduce the results.

There must also be a defect process: published results can be challenged with a reproducer, affected runs can be marked superseded without deletion, and a correction includes the scope, cause and uniform rescoring rather than selective model changes. A newly found critical false-pass defect blocks certification until resolved.

The promise should be **no known critical validity defect, no hidden assistance or selective treatment, independently checkable results, and precise disclosure of uncertainty**. Calling the outcome 100% accurate would go beyond what these tests can establish.

## Sources and evidence register

Live sources were consulted on September 13, 2026. Moving pages must be archived with dates/revisions during implementation; current documentation is not proof of historical server behavior. Research findings support the design choices; numerical release thresholds and schedules in this plan are proposed engineering judgments.

1. Qiskit community. [Qiskit HumanEval repository](https://github.com/qiskit-community/qiskit-human-eval). Formats and scope; pinned revisions are in the preflights.
2. QHE authors. [Qiskit HumanEval: An Evaluation Benchmark For Quantum Code Generative Models](https://arxiv.org/abs/2406.14712), 2024. Original benchmark research.
3. IBM. [Qiskit Code Assistant evaluation table](https://quantum.cloud.ibm.com/docs/en/guides/qiskit-code-assistant). Published scores and system-prompt qualification.
4. ScienceOne-AI. [ScienceEval](https://github.com/ScienceOne-AI/ScienceEval). Contextual published comparisons.
5. Jiawei Liu et al. [Is Your Code Generated by ChatGPT Really Correct?](https://arxiv.org/html/2305.01210v3), NeurIPS 2023. Test adequacy, valid inputs and mutation analysis.
6. Rishi Bommasani, Percy Liang and Tony Lee. [HELM overview](https://crfm.stanford.edu/2022/11/17/helm.html), November 2022. Controlled adaptation, coverage and multiple metrics.
7. Melanie Sclar et al. [Prompt-format sensitivity](https://arxiv.org/abs/2310.11324), ICLR 2024; initially October 2023. Effects of meaning-preserving formatting.
8. Rotem Dror et al. [The Hitchhiker's Guide to Testing Statistical Significance in NLP](https://aclanthology.org/P18-1128/), ACL 2018. Test selection and assumptions.
9. OpenAI. [HumanEval metric implementation](https://github.com/openai/human-eval/blob/master/human_eval/evaluation.py). Pass@k and sample accounting.
10. Mark Chen et al. [Evaluating Large Language Models Trained on Code](https://arxiv.org/abs/2107.03374), 2021. Code-generation evaluation context.
11. Naman Jain et al. [LiveCodeBench](https://arxiv.org/abs/2403.07974), initially March 2024; [project](https://livecodebench.github.io/). Time-segmented evaluation and contamination mitigation.
12. Matteo Paltenghi and Michael Pradel. [MorphQ](https://arxiv.org/abs/2206.01111), ICSE 2023. Quantum metamorphic testing.
13. Saumya Brahmbhatt et al. [Benchmarking LLMs on Repairing Qiskit Programs using Bugs4Q](https://arxiv.org/abs/2607.09007), July 2026 preprint. Runtime-dependent validity.
14. Mohammad Arif Rasyidi and Syahirul Faiz. [Benchmarking API Drift in LLM-Generated Quantum Code](https://arxiv.org/abs/2607.04072), July 2026 preprint. Version fidelity.
15. Timnit Gebru et al. [Datasheets for Datasets](https://arxiv.org/abs/1803.09010), initially 2018. Dataset documentation and maintenance.
16. EleutherAI. [lm-evaluation-harness interface](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md). Templates, configuration and logging.
17. Google. [Gemini 3.5 migration guidance](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.5). Sampling-override recommendations.
18. Google. [Firebase AI Logic parameters](https://firebase.google.com/docs/ai-logic/model-parameters). Unsupported/ignored controls; applicability requires model/endpoint verification.
19. Google. [Gemini 3.6 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash), updated July 30, 2026. Model identity and limits.
20. Qiskit community. [Issue 23](https://github.com/qiskit-community/qiskit-human-eval/issues/23), opened February 2026, now closed. Historical insufficient-test example, not asserted to remain unfixed locally.
21. Local evidence: the four new probe/inventory JSON files, `final-summary.json`, pinned preflights, current source and GitHub merge metadata. These support the current-state findings and their limits.

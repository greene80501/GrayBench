# GrayBench replacement engine

A Python 3.12 implementation of the [reliability plan](../docs/RELIABILITY_PLAN.md).
This engine is under development and is **not certified for model ranking**.
The root-level V2 package and its pilot results remain historical evidence.
Engine version 3 and graph protocol 4 are different version identifiers.

## Start here

Run from this directory:

```sh
uv sync --locked --extra dataset --extra qiskit
uv run graybench doctor
uv run graybench inventory ../data/datasets
uv run graybench --help
```

`inventory` imports the pinned 151 normal and 151 hard records and emits review
cards. Loading records or passing their reference tests does not admit them for
publication. The offline cohort excludes eight explicit service-dependent
families per suite, leaving 143 tasks each. See the
[complete graph reference scan](../docs/reliability-evidence/reference-scan-38db7fa.md).
`admission-inventory CACHE OUTPUT` writes a separate, content-addressed
protected-track review artifact with all 302 records pending. It keeps pinned
task ancestry, known findings, external-service status, and slots for revised
public contracts, positive and wrong-answer controls, and two independent
reviews. An empty structural checklist is not external verification;
`publication_eligible` remains false.

`oracle-review-inspect REVIEW.jsonl CACHE` checks a completed local authored
control run against the pinned task bytes. It verifies the event chain, case
identities, recorded expectations, source-manifest digest, and consistency of
the recorded judgments. Unexpected outcomes are listed rather than discarded.
Its `locally_verified` field means only internal consistency with pinned task
ancestry. A holder can rewrite an unsigned chain; the command cannot establish
semantic adequacy, reviewer identity, independence, or publication eligibility.
For the revised task-2 and task-20 value contracts, run the predeclared local
controls against an immutable Docker image:

```sh
uv run graybench protected-oracle-review CACHE REVIEW.jsonl --suite both --image sha256:IMAGE_DIGEST
uv run graybench oracle-review-inspect REVIEW.jsonl CACHE
```

The header freezes each source-bound protected judge manifest before any
candidate control executes. Inspection verifies every observed judgment against
that declaration. A failed or changed judge leaves an incomplete log. These
controls exercise numeric value semantics only, never native-object behavior.

Inventories written now use schema 2: their recorded creator-source digest is
historical provenance, while validation re-reads the exact pinned task bytes.
Older schema-1 inventories retain their original current-source check. This
lets task-card work survive unrelated engine edits without treating a copied
digest as authenticated source evidence. A legacy JSON inventory that omits
`schema_version` remains schema 1. To inspect local authored controls
against the entire inventory, run:

```sh
uv run graybench admission-control-audit INVENTORY.json CACHE AUDIT.json REVIEW1.jsonl REVIEW2.jsonl
```

The exclusive, content-addressed audit lists all 302 task cards, including
those with no controls, and names each control's artifact, case, task, expected
and actual outcome, and judge digest. It does not fill requirement evidence or
review attestations, infer semantic adequacy, or admit tasks. The saved control
logs must be available separately to reverify the audit.
The summary separates authored wrong controls that passed, authored correct
controls that failed, and other mismatches such as timeouts.
Report schema 5 verifies any recorded judge manifest against its digest and
requires a judge manifest predeclared in the log header, plus an exact
card-bound protected judge digest, before a control can support a requirement.
The judge identity includes the oracle and private cases, so an earlier oracle
cannot qualify merely because it shares a public contract. A matching
declaration is local, unsigned evidence, not independent attestation.

## Execution conditions

| Selection | Behavior | Current limitation |
|---|---|---|
| `upstream` (default) | Historical protocol-3 value transport and exact pinned tests | Known object-identity verdict defects; retained for explicit historical conditions |
| `upstream-graph-v4` | Protected protocol-4 judge with complete graph snapshots | Incomplete SDK coverage and resource calibration; candidate snapshot substitution is not attested |
| `upstream-graph-delta-v1` | Same graph validation with changed-record transport | Reduces wire traffic; still cannot attest a candidate's native return object |
| Named semantic revision | Explicitly revised task contract/test, frozen before generation | Development-only; not an upstream score or complete task certification |
| `qhe-pinned-native-v1` | Candidate and original pinned test run in one isolated Python/Qiskit process | Preserves native semantics, but same-process candidate code can inspect or tamper with tests; development-only |

There is no automatic fallback between these conditions. Semantic revisions
currently cover tasks 0, 2, 63, 82, 113, 116, 120 and 141. See
[evaluation recipes](../docs/reliability-evidence/evaluation-recipes.md),
[gate revisions](../docs/reliability-evidence/gate-semantics-revisions.md), and
[the registry](src/graybench/evaluation_recipes.py) for exact names and family checks.

The graph bridge is implemented and opt-in. It uses separate persistent arenas in
candidate and trusted judge containers; the host relays bounded data without
constructing candidate-supplied Qiskit objects. Its retained references, cycles,
mutation and selected SDK cache/owner semantics repair the six preserved identity
fixtures from the value-only bridge. Candidate code still shares a process with
its graph snapshot encoder and can substitute the serialized value; the
[protected task-2 probe](../docs/reliability-evidence/protected-worker-encoder-integrity.md)
reproduces that false pass. Thus graph transport does not establish arbitrary
Python or Qiskit equivalence or native-object integrity. See
[protected graph scope](../docs/reliability-evidence/protected-graph-development.md),
[delta transport](../docs/reliability-evidence/graph-delta-transport-development.md),
and [live capture validation](../docs/reliability-evidence/graph-live-capture-development.md).

Protected-track candidates have no private tests or reference answers mounted.
Native-track candidates share a process with the pinned test; this limitation is
recorded in each judgment. Neither track mounts credentials or the Docker socket.
Runtime images must use immutable local `sha256:...` IDs. Protected candidate
processes freeze between calls. Bootstrap and active-wall-time accounting are
explicit; resource ceilings remain subject to calibration. Candidate output has
no verdict authority. Unsupported interfaces and judge infrastructure failures
remain unscored blockers. Basic exception type/argument transport is bounded;
arbitrary exception metadata is not supported.
The [runtime reproduction recipe](runtime/README.md) freezes Debian packages
and checks a rebuilt image against the historical evaluator's installed-package
fingerprint. Matching that fingerprint does not certify benchmark scores.

## Campaigns and provenance

Adapters cover Ollama, OpenAI Chat Completions, OpenAI Responses, Gemini and a
development-only OpenAI-compatible Chat route. The latter has no assumed
metadata endpoint, requires an explicit unverified-discovery exception and
endpoint verification for any requested settings, and remains
publication-ineligible; see the
[compatibility route](../docs/reliability-evidence/openai-compatible-development.md).
OpenAI-compatible endpoints have explicit base URLs and model IDs; additional
native adapters use the `graybench.adapters` entry-point group. This is an
extension mechanism, not verified support for every model. Exact endpoint/model
settings need evidence. An accepted request setting is not proof the provider
honored it. No default helpful prompt, answer repair or hidden retry is added.
For a new API-backed campaign, the model specification must also declare a
public `credential_scope_id` such as `openai/project/graybench-evaluation`.
This is an operator label, not a credential or an independently authenticated
account ID. Use a provider/namespace/label form; a loaded key cannot occur
inside the label. Keep the key only in
`credential_env`. The transport records the
scope and a digest and length of the exact JSON bytes passed to HTTPX, while
recording only the names of authentication headers. New campaign plans freeze
one dispatch per sample; ambiguous 5xx responses stop the run without an
automatic replay. Historical manifests remain readable with their earlier
retry policy and without a scope label. New native and protected runs also
reject hand-edited retry policies at ledger creation. Older development tracks
retain their frozen retry conditions and cannot be reported as either new track.
When that environment variable is loaded, validation rejects its value in
public campaign setups, protocols, run contexts, prepared requests and paths,
model observations, deliveries and judgments before any ledger write or model
dispatch. Keep credentials out of public task inputs and adapter settings;
this check applies to the credential named by the model spec.
For response evidence, the transport separately hashes bounded encoded HTTP
entity bytes and decoded JSON bytes. It requests identity encoding and also
accepts bounded gzip and deflate responses. Already-decoded injected responses
cannot claim an encoded hash. See the
[response capture audit](../docs/reliability-evidence/response-entity-capture.md).
The transport also uses the supplied adapter instance for authentication and
discovery; see the [adapter consistency audit](../docs/reliability-evidence/adapter-instance-consistency.md).
New prepared requests freeze the non-secret headers GrayBench sends and the
names of supported credential fields. The transport checks HTTPX's built
request before network dispatch and records its non-secret headers; see the
[request-header audit](../docs/reliability-evidence/public-request-headers.md).
New requests and campaign protocols also bind a local adapter-code manifest;
see the [adapter provenance audit](../docs/reliability-evidence/adapter-code-provenance.md).

`campaign-plan` freezes selected tasks, requests, an explicit evaluation recipe
and `--extraction`. The default `raw_or_single_python_fence_v1` is retained.
The separate `unique_entrypoint_fence_v2` development condition can select
the sole Python block defining the public entry point from a multi-block
answer; duplicate alternatives and malformed fences reject. The selected
method and exact judge policy are retained in judgment evidence and cohort
identity. This is a labeled formatting-sensitivity condition, not an
automatic retry or repair. See the [extraction policy evidence](../docs/reliability-evidence/extraction-protocol-v2-development.md).
The separately versioned `unique_entrypoint_fence_v3` also recognizes
zero-to-three-space-indented backtick fences; its ambiguity controls and
[development evidence](../docs/reliability-evidence/extraction-protocol-v3-development.md)
remain distinct from both earlier policies. A small
[hosted provider check](../docs/reliability-evidence/hosted-generation-conformance-2026-09-27.md)
records real OpenAI and Google attempts without a certified score.
The [Ollama provider check](../docs/reliability-evidence/ollama-generation-conformance-2026-09-27.md)
records a separately frozen local run with the same task family and release
limitations.
Published 101-task Qiskit HumanEval results and why they cannot yet be compared
to this 151-task condition are recorded in the
[external baseline review](../docs/reliability-evidence/external-baseline-comparability.md).
`campaign-create` saves the validated setup without generating answers.
`campaign-step` performs at most one scheduled generation or protected judgment;
it may make a billable request. `campaign-observe` records provider metadata.
`native-plan` freezes one pinned normal or hard suite, an immutable image,
exclusions, extraction policy, requests and judge limits. Its default
`offline_143` population excludes the eight known external-service tasks;
`custom_development` requires explicit `--task` keys and cannot be labeled a
143-task score. `native-create` saves the run without generation, and
`native-step` performs at most one generation or native judgment. A step may
make a billable model request. Run `campaign-observe` with the native ledger to
record provider metadata. For example:

```sh
uv run graybench native-plan MODEL_SPEC.json CACHE SETUP.json --name trial --label 'pinned normal offline' --suite normal --image sha256:IMAGE_ID
uv run graybench native-create SETUP.json CACHE LEDGER.sqlite
uv run graybench campaign-observe LEDGER.sqlite RUN_ID
uv run graybench native-step LEDGER.sqlite RUN_ID CACHE
uv run graybench summary LEDGER.sqlite RUN_ID
```

The default `raw_or_single_python_fence_v1` extraction accepts a raw normal
function-body suffix or a complete replacement function (and one Python code
fence). For a **normal-suite exact prompt suffix** condition, add
`--extraction exact_prompt_suffix_v1` to `native-plan`. That condition
concatenates the public prompt and raw response without choosing a code block
or replacing the prefix. Valid top-level helpers and replacement definitions
remain possible when they form valid Python, as with ordinary code completion.
It is unavailable for hard tasks, whose
public contract requests a standalone function. Plans and reports expose the
policy, and comparisons reject different policies; see the
[answer-format evidence](../docs/reliability-evidence/native-answer-format-conditions.md).

Native plans also freeze an exception policy. The default
`conservative_unattributed_v1` preserves historical behavior: when a pinned
test raises a non-assertion exception after the candidate returns, the outcome
is `infrastructure_error` and the run remains unscored. Add
`--exception-policy test_exception_is_failure_v1` to count a completed
test-phase exception as a failed candidate answer. Candidate-code exceptions
remain `candidate_error`; Docker, timeout, missing-result and result-integrity
failures retain their separate outcomes. The selected policy is bound in the
cohort, protocol and judge manifest, shown in summaries, and cannot be mixed
in paired comparisons. Both conditions remain development-only. The
[286-case diagnostic](../docs/reliability-evidence/native-null-return-screen.md)
shows why the distinction matters; task admission must still establish oracle
adequacy and stability before either condition can support publication. The
[policy record](../docs/reliability-evidence/native-exception-policy.md)
defines both outcomes and their limits.

`native-reference-scan` runs pinned canonical answers through the same native
judge without making model requests or scores. It writes a new append-only,
source-bound evidence file; an existing path is never overwritten. By default
it scans the 143 offline tasks in one suite. Use repeated `--task` keys for a
declared subset, or `--include-external` to deliberately include the eight
service-dependent tasks. The extraction policy must be supplied explicitly.
Use `--exception-policy` to calibrate the same exception condition as a native
plan; omission selects the historical conservative condition.
Normal exact-suffix and hard standalone conditions
remain separate:

```sh
uv run graybench native-reference-scan CACHE NORMAL.jsonl --suite normal --image sha256:IMAGE_ID --extraction exact_prompt_suffix_v1
uv run graybench native-reference-scan CACHE HARD.jsonl --suite hard --image sha256:IMAGE_ID --extraction raw_or_single_python_fence_v1
uv run graybench reference-inspect NORMAL.jsonl
```

One canonical pass establishes only that the pinned test can execute that
reference once in the specified image. It does not establish test stability,
oracle adequacy, or publication eligibility. See the
[native calibration evidence](../docs/reliability-evidence/native-reference-calibration.md).

The native report names exactly one suite, population and denominator. It never
combines normal and hard, and `publication_eligible` remains false until task
admission and independent reproduction are complete.

`protected-plan` supports separately versioned value contracts for task 2
(Bell amplitudes) and task 20 (GHZ amplitudes) as development examples. One or
both may be selected with repeated `--task` arguments in a single normal or
hard suite. It freezes the revised public contracts, private semantic cases, a
pinned image, exact provider requests, and an explicit exclusion for every
unscheduled task before generation. The candidate returns bounded numeric
values; the trusted host checks them without treating them as proof of native
Qiskit objects or construction steps. `protected-create` records the plan
without a model request, and `protected-step` performs at most one generation
or judgment. A generation step may be billable. For example:

New task-20 plans select the `task20-seven-qubit-ghz-amplitudes-all-layouts-v2`
oracle. It tests all 210 ordered layouts allowed by the public value contract.
The earlier three-layout v1 oracle remains separately identifiable for saved
development evidence; its score is not interchangeable with v2. See the
[versioned control replay](../docs/reliability-evidence/task20-all-layouts.md).

```sh
uv run graybench protected-plan MODEL_SPEC.json CACHE SETUP.json --name trial --label 'two value tasks' --suite normal --task normal/qiskitHumanEval/2 --task normal/qiskitHumanEval/20 --image sha256:IMAGE_ID
uv run graybench protected-create SETUP.json CACHE LEDGER.sqlite
uv run graybench campaign-observe LEDGER.sqlite RUN_ID
uv run graybench protected-step LEDGER.sqlite RUN_ID CACHE
uv run graybench summary LEDGER.sqlite RUN_ID
```

This example has a two-task `custom_development` denominator, not an unchanged
QHE or 143/151-task score. Selecting only one task gives a one-task denominator.
All 302 pinned source cards remain pending independent admission review; see
the [task-2](../docs/reliability-evidence/protected-task2-value-development.md)
and [task-20](../docs/reliability-evidence/protected-task20-value-development.md)
development evidence.
Use each command's `--help` for required arguments. See
[model discovery](../docs/reliability-evidence/model-discovery.md) and
[evaluation recipes](../docs/reliability-evidence/evaluation-recipes.md).
For task 82's explicit `task82-file-semantic-v1` or `task82-file-semantic-v2`
recipe, `campaign-plan --parser-image sha256:...`
freezes a separate patched QPY parser runtime while candidate and oracle use
`--image`. This remains a development-only recipe; see the
[task 82 evidence](../docs/reliability-evidence/task82-semantic-track.md).

The append-only ledger binds schedules, requests, returned answers, judgments,
artifacts and event history. Source, environment, image and configuration
identities are recorded. Ambiguous dispatch or interrupted judgment blocks
automatic replay. Provider name and discovery checks detect specified metadata
changes; they cannot verify proprietary model weights. Development discovery is
required before campaign dispatch for adapters with metadata endpoints. An
adapter without one may use a frozen, reasoned `unverified_development` exception;
those runs retain a publication blocker. Live capability calibration remains
required for release.

Model specs may include an exact-model `capability_profile` with dated
documentation, request-probe digests, declared control support and token
limits. Its digest travels with new prepared requests. Reports distinguish
this operator evidence from effective settings, which remain unattested by a
successful request alone. See the
[capability evidence contract](../docs/reliability-evidence/provider-capability-evidence.md).
`capability-probe MODEL_SPEC OUTPUT` makes one non-benchmark provider request
and saves a non-secret record. All three plan commands accept repeated
`--capability-probe PATH` arguments and embed every cited accepted probe in
their setup. A bare digest cannot qualify a new campaign. The local record
verifies request acceptance and consistency, not effective decoding or provider
weight identity.

`verify-ledger` validates retained evidence. `summary` reports completeness and
score blockers before accuracy. `comparison-plan` and `compare` accept matched
historical, native, or protected-semantic setup files and retain paired task
families during resampling. They reject mixed tracks, suites, populations,
exclusions, judge conditions and incomplete source/request ancestry. Results
remain development-only and do not certify equivalent provider settings. See
[report integrity](../docs/reliability-evidence/summary-integrity.md),
[row bindings](../docs/reliability-evidence/event-row-bindings.md), and
[comparisons](../docs/reliability-evidence/paired-comparisons.md) and the
[dual-track comparison audit](../docs/reliability-evidence/dual-track-comparison.md).
Hashes and SQLite append rules are not external authenticity guarantees.

If a protocol 3.3 attempt has a saved post-request model observation but its
timing check was interrupted, run
`graybench recover-post-check LEDGER.sqlite ATTEMPT_ID`. The command verifies
the ledger, appends one timing check using the current clock, and does not call
the model or repeat the answer. A late or
backward-clock check remains a timing violation and cannot yield a score.
Missing post observations and unresolved deliveries require separate
adjudication; this command cannot synthesize them.

## Reference and regression checks

```sh
uv run graybench reference-scan CACHE NEW_OUTPUT --image sha256:IMAGE_ID --offline --bridge-protocol 4
uv run graybench reference-inspect NEW_OUTPUT
uv run --extra qiskit --extra dataset pytest
uv run ruff check src tests
uv run ruff format --check src tests
```

Replace the uppercase placeholders. Add `--docker PATH` when Docker is not on PATH.
The reference CLI selects full snapshots for protocol 4; delta reference probes
currently use the Python API described in the delta document. Output files are
reserved exclusively and are never overwritten. A pending invocation needs
adjudication, not an automatic rerun. Reference calibration is not LLM accuracy.

For protected regression tests, set `GRAYBENCH_TEST_IMAGE` to the inspected immutable
Python 3.12 evaluation image and, if needed, `GRAYBENCH_DOCKER` to its executable.
Without the image setting, Docker tests skip. On source-manifest digest
`ea0f22f9f5b30d12fe8f6cb8fa5b23dc1fa174c230489604e8580c302390655d`,
the complete pinned-image regression before adding four graph-integrity controls
had 1,130 passed, one experimental skip and two expected failures. The current
focused task-2 protected suite has 18 passed and six expected failures; the
current offline suite has 912 passed and 225 protected skips. These expected
failures preserve [known encoder integrity defects](../docs/reliability-evidence/protected-worker-encoder-integrity.md),
not a release-ready score. Green controls do not establish every benchmark
requirement.

The latest complete graph reference scan, at `77f29ff`, records **122 pass,
19 unsupported, one fail and one infrastructure error in normal**, and **123
pass, 19 unsupported and one infrastructure error in hard**. The extra hard
pass is task 63's unstable canonical answer, not a compatibility gain. See the
[complete comparison](../docs/reliability-evidence/reference-scan-77f29ff.md)
for source, task identities, exclusions, raw outcomes and unresolved cases.

## Remaining admission work

- Complete SDK/interface fidelity and uniform resource calibration, including long
  repeated-call workloads. No object-history dropping to manufacture a pass.
- Audit every public requirement with valid alternatives and meaningful mutants.
  [Known oracle defects](../docs/ORACLE_REVIEW_FINDINGS.md) remain separate from
  transport compatibility. Task 63's private RNG assumption and task 82's file
  boundary need explicit conditions or revisions.
- Validate live provider capabilities, effective settings and model provenance;
  freeze assistance, budgets, sampling and recovery before a campaign.
- Complete fresh holdout design, independent reproduction, external release
  signing and requirement-by-requirement review. Preserve all earlier evidence.

Green tests and passing canonical solutions do not make a benchmark fair or its
oracles adequate. Publication eligibility remains false until those gates pass.

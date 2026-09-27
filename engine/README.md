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

## Execution conditions

| Selection | Behavior | Current limitation |
|---|---|---|
| `upstream` (default) | Historical protocol-3 value transport and exact pinned tests | Known object-identity verdict defects; retained for explicit historical conditions |
| `upstream-graph-v4` | Protected protocol-4 judge with complete graph snapshots | Incomplete SDK coverage and resource calibration |
| `upstream-graph-delta-v1` | Same graph validation with changed-record transport | Reduces wire traffic; still captures and reconstructs retained object history |
| Named semantic revision | Explicitly revised task contract/test, frozen before generation | Development-only; not an upstream score or complete task certification |

There is no automatic fallback between these conditions. Semantic revisions
currently cover tasks 0, 63, 82, 113, 116, 120 and 141. See
[evaluation recipes](../docs/reliability-evidence/evaluation-recipes.md),
[gate revisions](../docs/reliability-evidence/gate-semantics-revisions.md), and
[the registry](src/graybench/evaluation_recipes.py) for exact names and family checks.

The graph bridge is implemented and opt-in. It uses separate persistent arenas in
candidate and trusted judge containers; the host relays bounded data without
constructing candidate-supplied Qiskit objects. Its retained references, cycles,
mutation and selected SDK cache/owner semantics repair the six preserved identity
fixtures from the value-only bridge. That does not establish arbitrary Python or
Qiskit equivalence. See [protected graph scope](../docs/reliability-evidence/protected-graph-development.md),
[delta transport](../docs/reliability-evidence/graph-delta-transport-development.md),
and [live capture validation](../docs/reliability-evidence/graph-live-capture-development.md).

Candidates have no private tests, reference answers, credentials or Docker socket
mounted. Runtime images must use immutable local `sha256:...` IDs. Candidate
processes freeze between calls. Bootstrap and active-wall-time accounting are
explicit; resource ceilings remain subject to calibration. Candidate output has
no verdict authority. Unsupported interfaces and judge infrastructure failures
remain unscored blockers. Basic exception type/argument transport is bounded;
arbitrary exception metadata is not supported.

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

`campaign-plan` freezes selected tasks, requests, an explicit evaluation recipe
and `--extraction`. The default `raw_or_single_python_fence_v1` is retained.
The separate `unique_entrypoint_fence_v2` development condition can select
the sole Python block defining the public entry point from a multi-block
answer; duplicate alternatives and malformed fences reject. The selected
method and exact judge policy are retained in judgment evidence and cohort
identity. This is a labeled formatting-sensitivity condition, not an
automatic retry or repair. See the [extraction policy evidence](../docs/reliability-evidence/extraction-protocol-v2-development.md).
`campaign-create` saves the validated setup without generating answers.
`campaign-step` performs at most one scheduled generation or protected judgment;
it may make a billable request. `campaign-observe` records provider metadata.
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

`verify-ledger` validates retained evidence. `summary` reports completeness and
score blockers before accuracy. `comparison-plan` and `compare` require matched,
complete protocols and keep normal/hard task families together during paired
resampling. See [report integrity](../docs/reliability-evidence/summary-integrity.md),
[row bindings](../docs/reliability-evidence/event-row-bindings.md), and
[comparisons](../docs/reliability-evidence/paired-comparisons.md).
Hashes and SQLite append rules are not external authenticity guarantees.

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
Without the image setting, Docker tests skip. At source commit `124e43f`, the
pinned Python 3.12 runtime passed 1,083 tests with one experimental skip and
zero failures or errors; see the [extraction-policy development record](../docs/reliability-evidence/extraction-protocol-v2-development.md).
That result covers the regression suite, not every benchmark requirement.

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

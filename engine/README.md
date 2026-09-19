# GrayBench 3 replacement engine

This is a fresh Python 3.12 implementation of the accepted
[reliability plan](../docs/RELIABILITY_PLAN.md). It is under construction. The root-level V2
package remains available to reproduce historical pilots. Do not mix its scores with this engine.

From this directory:

```sh
uv sync --locked --extra dataset --extra qiskit
uv run graybench doctor
uv run graybench inventory ../data/datasets
uv run pytest
uv run ruff check src tests
```

The inspection CLI does not launch a billable benchmark campaign. The full-suite runner will
be exposed after the required interfaces and oracle gates are implemented. Generation adapters
can currently be exercised programmatically with explicit frozen requests.

## Implemented foundation

- Strict public-task and experiment contracts, with exact request hashes frozen before dispatch.
- Independent identities for dataset, generation code, runtime, judge, and analysis.
- Native Ollama, OpenAI Chat Completions, OpenAI Responses, and Gemini request/response adapters.
  OpenAI-compatible endpoints can use their own model IDs and base URLs. Additional native
  interfaces register through the `graybench.adapters` package entry-point group.
- Explicit model settings with evidence. Unknown, ignored, or unsupported requested settings
  fail before generation. No default temperature, helpful prompts, tools, or answer repair.
  An accepted setting is not falsely represented as provider-confirmed effective behavior.
- Single-attempt bounded HTTP transport, no redirects or automatic retries, API keys sourced
  from named environment variables, credential echoes redacted from recorded responses.
- An append-only SQLite ledger with frozen schedules, exclusive dispatch claims, bounded retry
  eligibility, immutable returned answers and judgments, content hashes, and an event chain.
  A database owner can still rewrite SQLite itself; the chain is not an external signature.
- Incomplete or unsupported judgments produce no aggregate accuracy score. Historical rescoring
  by a different judge cannot alter the frozen experiment's reported score.
- A candidate-only Docker worker: no tests, reference answers, credentials, or Docker socket
  are mounted. The host decodes bounded plain values and makes the correctness decision.
  Candidate stdout has no verdict authority. Runtime images must use immutable local IDs.
- A bounded circuit codec exchanges standard instructions, registers, global phase,
  and initial/routing permutations using a fixed constructor registry. No QPY or pickle is
  deserialized. Circuit wire v4 preserves parameter UUIDs, vector ordering and a bounded fixed
  vocabulary of symbolic operations. Reconstruction uses the pinned Qiskit 2.4 structured replay
  interface, never expression-string evaluation. Custom instructions, open controls and control
  flow remain unsupported. Matrix-defined UnitaryGate instructions preserve their numeric data
  without repairing nonunitary values, and supported instruction labels survive transport.
  It is not a complete serialization of circuit metadata or original virtual-qubit identity.
- StatePreparation preserves its original argument, current parameters, label/int mode and
  inverse flag. Reconstruction does not normalize again. Normal and hard tasks 5 and 6 pass
  targeted reference checks; modified/cached definitions and cross-object aliases still need
  an explicit representation before complete SDK equivalence can be claimed.
- Explicit `call_with_updates` records changed arguments. The simpler read-only call refuses
  to silently discard mutations. An upstream-compatible mutation/alias bridge is still required.
- Numeric arrays and NumPy scalars retain dtype, byte order, shape and exact numeric bytes;
  object/string/structured dtypes and oversized allocations are rejected. Statevectors,
  density matrices and rectangular operators retain their subsystem dimensions. Complex
  array values, signed zero and non-finite numeric array values are not silently repaired.
- Clifford and unseeded StabilizerState values retain their boolean tableaux and phase bits;
  Choi channels retain numeric data and input/output subsystem dimensions. Invalid symplectic
  or nonphysical values are not repaired. Explicit RNG state and bound subsystem arguments
  remain unsupported for these new representations.
- `Candidate.call_wire` forwards typed data without host object reconstruction. `ProtectedJudge`
  runs fixed trusted semantic oracles in a separate container with disjoint mounts and bounded
  memory, CPU, wall time and output. Its provenance binds source files, image, resource policy
  and exact input hash. Judge failures remain unscored infrastructure outcomes. The current
  registry contains the task-20 behavioral oracle; the full upstream-test bridge is unfinished.
- `UpstreamJudge` now runs the pinned upstream `check` function in a separate trusted container
  and proxies calls into the candidate container without host object reconstruction. It records
  complete bounded wire transcripts and source/input identities, invokes `check` once, and
  preserves candidate state between calls. Input mutation and unsupported value interfaces
  remain explicit unresolved outcomes. Non-assertion test errors remain unscored pending review.
- The first full reference-interface scan ran all 143 offline tasks in each suite: 80 passed
  in each, with the other outcomes retained for diagnosis. This is not model accuracy. It exposed
  register-backed bit identity loss; circuit wire format v2 fixes that and all four affected
  normal/hard task-38/task-87 cases pass a separate replay. Full scan and replay remain distinct.
- Targeted symbolic and NumPy-parameter replays now pass tasks 7, 8, 9, 99, 111 and 127 in both
  suites. This is compatibility evidence, not a rerun of the full scan or task certification.
- Worker protocol 3 separates execution exceptions from decoding/encoding diagnostics. Codec
  diagnostics produce unscored unsupported outcomes pending adjudication. A candidate can spoof
  such a diagnostic, but cannot earn a pass or complete aggregate score through it.
- A separate strengthened task-20 oracle checks mapped GHZ+ state fidelity, following final
  logical-qubit positions and accepting global phase. Two positive constructions pass and four
  shape-compatible mutants fail. It does not prove which pass-manager algorithm generated a
  returned circuit; that specification requirement remains unverified.
- Strict byte-pinned imports of all 151 normal and 151 hard Qiskit HumanEval records, public/private
  record separation, and an explicit review inventory. External-service membership is provisional
  and must be reviewed; no task becomes eligible merely because its reference happens to pass.
- Relevant environment, package, complete engine source, and NVIDIA GPU provenance. Ollama
  discovery preserves server version, model details, tags/digests, and loaded-model observations.

## Required work before release

1. Rich, bounded Qiskit value codecs; mutations to arguments; files; transformation-pass callbacks;
   type fidelity; and complete upstream-proxy semantics through the independent judge. The current
   scientific-value/numeric-circuit worker is not a complete Qiskit executor. Candidate-reported
   errors are untrusted.
   Candidate containers now freeze between calls, so judge delays do not consume their active
   wall-time allowance and background processes cannot run for free. Startup and lifecycle
   overhead are conservatively charged. Calibration of these overheads remains required before
   choosing published execution limits; this is an active wall-time policy, not CPU accounting.
   A persistent local Docker API connection handles pause/unpause without launching a CLI
   process for every call. This resolves the reproduced task-109 reference timeout caused by
   the cost of 1,000 call boundaries. Remote Docker control endpoints are not supported here.
2. Reviewed specifications and stronger semantic oracles for every admitted task, independent
   positive implementations, and meaningful mutants. The strengthened task-20 behavioral oracle
   rejects the reproduced empty-circuit false acceptance, but its complete specification review
   is unfinished. The inventory explicitly marks every task unreviewed.
3. Complete campaign orchestration with model drift checks, full provenance and eligibility
   before generation. `GenerationRunner.step()` now dispatches at most one frozen request,
   checks source/request/endpoint identities, and resumes from the ledger. Retry backoff is
   enforced transactionally across restarts; pending/ambiguous delivery stops dispatch.
   `UpstreamCampaign` now binds the supplied task records, per-task judge configurations and
   immutable image before dispatch, and schedules protected judgments from saved answers.
   Judgment intent is append-only; interrupted oracle execution stops rather than rerolling.
   `campaign-create SETUP CACHE LEDGER` saves a validated development setup without generation;
   `campaign-step LEDGER RUN_ID CACHE [--docker PATH]` resumes at most one action using the
   stored setup. The setup includes a frozen Protocol, image, execution and HTTP limits.
   Python/OS/package/source provenance is stored append-only and checked before CLI resume.
   `campaign-plan MODEL CACHE OUTPUT --image IMAGE --name NAME --suite both` builds that setup
   offline from both full pinned suites; use `--task SUITE/TASK_ID` repeatedly for an explicit
   selection. `--repeats N` and an optional UTF-8 `--system-prompt FILE` are frozen in the plan.
   Existing output files are not overwritten. Known external-service tasks are reported, not
   silently filtered. Task adequacy/admission reviews and model drift checks remain
   required. Identity validation does not certify an oracle or make a cohort release-eligible.
   Protocol 3.1 requires returned model names to match the requested name or an explicit
   `accepted_returned_models` list backed by `model_identity_evidence`. Missing/unexpected
   names retain answers but stop dispatch and suppress aggregate accuracy. This is a provider
   name check, not weight verification. Protocol 3.0 runs need their original engine for replay.
   `campaign-observe LEDGER RUN_ID` saves provider discovery evidence. Once a baseline exists,
   generation steps refresh it before dispatch; missing/changed discovery identity stops the
   run and suppresses aggregate accuracy. Ollama comparison uses the exact catalog model digest,
   server version and show configuration; volatile load state remains recorded separately.
   Discovery is currently optional for development runs. Hosted metadata extraction is
   implemented; effective-setting and model-native capability validation remain incomplete.
4. Provider capability evidence and live contract checks; model-native budget calibration;
   independent reproducibility runs; repeated/paired statistical analysis; published-score
   compatibility records; and a release manifest anchored outside candidate execution.
5. Migration of the user-facing commands and documentation to the replacement once its gates pass.

No existing result has become a certified score merely because these foundation tests pass.
Development summaries use the frozen schedule denominator, expose per-task outcomes
and score blockers, and require the frozen analysis source. See
[report integrity](../docs/reliability-evidence/summary-integrity.md) for snapshot
consistency, provenance checks and the remaining publication requirements.
New ledgers also bind exact database records into their event history. The
[row-binding verifier](../docs/reliability-evidence/event-row-bindings.md) rejects
unrecorded or inconsistent answers/judgments. Legacy logs require their original engine.

`comparison-plan` and `compare` provide explicit development comparisons with paired
task-family resampling. They require matched, complete protocols and retain normal/hard
variants together. See [paired comparisons](../docs/reliability-evidence/paired-comparisons.md)
for commands, statistical assumptions and the remaining calibration requirements.

`campaign-observe` now supports model-specific metadata from OpenAI Chat/Responses
and Gemini as well as Ollama. [Discovery evidence](../docs/reliability-evidence/model-discovery.md)
describes raw HTTP records, conservative drift blocking and the distinction between
provider-reported metadata and verified effective settings.

## Adversarial Docker tests

`campaign-plan --evaluation-recipe NAME` explicitly selects the existing task 0,
82, 113 or 141 development revision. Selection is frozen before generation and checked
on resume and comparison; wrong-family cohorts fail rather than being filtered.
See [evaluation recipes](../docs/reliability-evidence/evaluation-recipes.md) for
commands, source replay rules and the distinction from upstream scores.

Runtime preparation and candidate execution use an explicit startup handshake.
Bootstrap failures remain unscored and bootstrap time is excluded from the candidate
budget; see [runtime attribution](../docs/reliability-evidence/runtime-bootstrap.md).

Circuit wire v5 supports bounded nested definitions for plain Qiskit Gate/Instruction
objects and selected standalone standard instructions, with names and JSON metadata.
See [instruction transport](../docs/reliability-evidence/instruction-definitions.md)
for validated cases, limits and remaining subclass/cache restrictions.
ScalarOp and SparsePauliOp now have bounded data-only exchange preserving terms,
phases, symbolic coefficients and subsystem bindings; see [operator evidence](../docs/reliability-evidence/sparse-operators.md).

The reusable oracle-review runner records authored counterexamples separately from
model scores. [Task0/1 review](../docs/reliability-evidence/task0-1-review.md) reproduces
upstream false accepts and documents the explicit task0 size revision. Task1 still
needs a contract decision about what returned counts can establish.

Candidate output files can be captured as opaque bytes while all candidate processes
remain frozen. The isolated workspace uses a bounded ephemeral tmpfs volume. See
[file capture](../docs/reliability-evidence/file-capture.md) for the initial boundary
and limitations; capture alone does not establish file correctness.
The separate development `QpyFileJudge` now implements a three-container task-82
[semantic track](../docs/reliability-evidence/task82-semantic-track.md). It is not
silently enabled for upstream campaigns and remains release-ineligible.

Large circuit exchange uses bounded lossless compression without removing gates.
Wire capacity failures remain unscored; diagnostic floods remain resource failures.
See [transport calibration](../docs/reliability-evidence/large-circuit-transport.md)
for limits, adversarial checks and separate normal/hard task-100 reference evidence.

`reference-scan CACHE OUTPUT --image IMAGE --offline` calibrates both pinned offline reference
suites into a new append-only JSONL file. Omit `--offline` only for an explicitly planned full
service-dependent calibration. `reference-inspect OUTPUT` checks its event chain and identifies
pending invocations. These commands produce compatibility evidence, never LLM accuracy scores.

Set `GRAYBENCH_TEST_IMAGE` to the locally inspected `sha256:...` image ID and optionally
`GRAYBENCH_DOCKER` to the Docker executable. Run `uv run pytest`. Docker tests are explicitly
skipped without that image setting. The image must have Python 3.12; Qiskit support will use the
separately pinned evaluation environment. Never point these tests at a privileged custom wrapper.

## Provider references

- [Ollama chat](https://docs.ollama.com/api/chat),
  [model tags](https://docs.ollama.com/api/tags), and
  [documentation index](https://docs.ollama.com/llms.txt).
- [OpenAI Responses reference](https://developers.openai.com/api/reference/typescript/resources/responses/methods/create).
- [Gemini generateContent](https://ai.google.dev/api/generate-content).

Endpoint support and settings still require evidence for the exact model and server version.

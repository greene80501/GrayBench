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
2. Reviewed specifications and stronger semantic oracles for every admitted task, independent
   positive implementations, and meaningful mutants. The strengthened task-20 behavioral oracle
   rejects the reproduced empty-circuit false acceptance, but its complete specification review
   is unfinished. The inventory explicitly marks every task unreviewed.
3. Complete campaign orchestration with model drift checks, full provenance and eligibility
   before generation. `GenerationRunner.step()` now dispatches at most one frozen request,
   checks source/request/endpoint identities, and resumes from the ledger. Retry backoff is
   enforced transactionally across restarts; pending/ambiguous delivery stops dispatch.
   Admission, judge scheduling and the user-facing campaign CLI remain required. This internal
   generation component is not a release eligibility check or a complete scoring runner.
4. Provider capability evidence and live contract checks; model-native budget calibration;
   independent reproducibility runs; repeated/paired statistical analysis; published-score
   compatibility records; and a release manifest anchored outside candidate execution.
5. Migration of the user-facing commands and documentation to the replacement once its gates pass.

No existing result has become a certified score merely because these foundation tests pass.

## Adversarial Docker tests

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

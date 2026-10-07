# GrayBench 2

**Replacement in progress:** the fresh Python 3.12 engine is in [engine/](engine/README.md).
The V2 implementation below is retained for historical pilot reproduction. Its judge has a
reproduced verdict-forgery vulnerability and its upstream oracles have known false acceptances;
V2 scores are not certified. See the [reliability plan and evidence](docs/RELIABILITY_PLAN.md).
The [complete normal/hard pair audit](docs/reliability-evidence/artifacts/qhe-pair-audit-2026-10-07/README.md)
records a contradictory task-41 prompt and undisclosed judge requirements; task admission remains unfinished.

Reproducible evaluation of Qiskit code generation on the official **Qiskit HumanEval normal and hard** suites. These are not Humanity's Last Exam or the generic Python HumanEval benchmark.

See [evaluation methodology](docs/METHODOLOGY.md) and [published comparison references](docs/COMPARISONS.md). Scores describe success on a particular dataset and environment; no benchmark can promise 100% correctness or eliminate unknown training contamination.

## Setup (Python 3.12)

```sh
git clone https://github.com/greene80501/GrayBench.git
cd GrayBench
uv sync --locked --extra dev
```

The project pins Python 3.12 and the Qiskit runtime stack. `uv.lock` locks transitive dependencies. `requirements.lock` is a hash-checked export used by the evaluator container. Run `uv lock` and regenerate that export deliberately when updating dependencies; revalidate references afterward.

Create a local `.env` using `.env.example`. Keep it out of source control. `graybench models check` checks presence, not remote authentication. Model lists are examples; exact API snapshot IDs are accepted.

## Validate before spending

```sh
# Read-only dataset inspection and planning
uv run graybench dataset -s normal
uv run graybench run -p openai -m gpt-4o-mini-2024-07-18 -s normal --dry-run

# Local reference audit only (never executes model output)
uv run graybench validate canonical -s normal --backend local -o data/local-normal.json

# Build a disposable Linux evaluator with Graphviz and the locked dependencies
docker build -t graybench-evaluator:2.0 .
uv run graybench validate canonical -s normal --backend docker -o data/preflight-normal.json
uv run graybench validate canonical -s hard --backend docker -o data/preflight-hard.json
```

Reference validation writes a complete report even when some references fail and exits nonzero in that case. Inspect the report. Its eligible task IDs are frozen before generation; unavailable tasks remain listed with reasons. Live runs accept only Docker preflights, and use their immutable image IDs. Changing dependencies, dataset identity or task selection changes comparability.

The offline profile excludes external IBM-service tasks. It does not substitute fake successes. A partial validated set is explicitly an **offline subset**, not an official full-suite score.

## Run a benchmark

```sh
uv run graybench run -p openai -m gpt-4o-mini-2024-07-18 -s normal --preflight data/preflight-normal.json --max-tokens 16384 --budget 5 -o results/openai-normal
uv run graybench run -p google -m gemini-3.6-flash -s hard --preflight data/preflight-hard.json --max-tokens 16384 --budget 10 -o results/google-hard
```

`--budget` is a per-run estimated USD ceiling, checked conservatively before requests. It is not a provider billing limit. Verify rates and account billing before large runs. Unknown pricing blocks automatic live runs. For a smoke test, add `--limit 3`; never compare that score with a full run.

`--prompt-profile environment` is a separate exploratory track that uniformly discloses the installed SDK versions and requests code only. The default `official` profile adds no system message. Never mix their scores.

One returned answer per task; no repair, test feedback, tools or extra attempt for an empty response. Only explicit rate-limit errors may be retried. The default cap is 16,384 output tokens. Reasoning models can consume their limit without delivering an answer; retain finish reasons and compare caps as separate experiments. Actual provider settings are saved with responses. Temperature zero is not a guarantee of deterministic output.

The evaluator has no network, credentials, user-profile mount or host repository mount, runs as an unprivileged user, and has CPU/memory/process limits. Only disposable task files are mounted, read-only. This reduces execution risk; it does not prove that hostile code cannot exploit a runtime flaw or inspect in-process tests.

## Results

```sh
uv run graybench results list
uv run graybench results show RUN_ID --verbose
uv run graybench results leaderboard -s hard
uv run graybench results export --run RUN_ID --output results/export
uv run graybench results rescore RUN_ID --preflight data/preflight-normal.json --output results/rescored.json
uv run pytest
```

Results default to `data/results.db`. JSONL exports include prompts, full responses, usage and outcomes. Comparison groups separate datasets, selected tasks, runtime images, settings and agent-system tracks. Historical unvalidated runs remain accessible through results list/export but are not silently mixed into the new comparison groups. A rescore writes a separate report and preserves the original run and answers; it makes no provider requests. Unknown cost stays unknown. Scores include Wilson intervals and numerator/denominator; incomplete and duplicate attempts cannot be marked complete.

A sweep YAML may contain `provider`, `models`, `suite`, `preflight`, `budget` and `max_tokens` per entry. Budgets apply per model run; a sweep is not a single shared spending allowance. GrayGate is a separate agent-system integration and has no assumed zero cost or fabricated token counts.

## Development

```sh
uv run pytest
uv run ruff check graybench tests --select E9,F63,F7,F82
uv run black --check graybench tests
```

Normal-suite prefixes and hard-suite argument contracts are part of the official task. Never strip required interfaces in pursuit of a harder test, patch generated imports, modify tests to fit model outputs, or select favorable repeated runs.

MIT licensed application; the upstream dataset is Apache-2.0. See upstream dataset terms and attribution in [methodology](docs/METHODOLOGY.md).

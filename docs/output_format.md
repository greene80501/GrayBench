# Output format v2

SQLite defaults to `data/results.db`, configurable with `GRAYBENCH_DB_PATH`. The compatible schema still uses `runs`, `attempts` and `scores`; protocol identity is separate from database schema version.

`runs.environment_info` is a JSON-encoded string containing host packages and a manifest: protocol, dataset size, task IDs, coverage, prompt/extraction policy, generation extras, reference fingerprint, Docker image ID, evaluator code fingerprint and budget estimate. The nominal temperature field is not a replacement for actual request parameters.

Each attempt preserves prompt, raw completion, extracted code, outcome, errors, bounded stdout/stderr, generation/execution timing, usage and estimated cost. `raw_response` is a JSON-encoded string; `graybench_request` inside it records actual provider arguments. Provider responses also retain resolved model versions and finish reasons when supplied. Credentials are not recorded.

Unknown cost is NULL, not zero. API errors may have unknown usage because a failed response does not prove zero billing. Empty returned completions preserve their reported usage. Operational API failures invalidate completion; generated-answer failures stay in the denominator. Duplicate/missing planned attempts cannot be marked complete.

Scores expose numerator, denominator, pass rate, failure counts, usage, estimated costs and Wilson 95% limits. Invalid or incomplete runs have no publishable score. Leaderboard exports include comparison cohort IDs; they are not an unconditional ranking of all historical runs.

## Exports

`results export --run RUN_ID -o DIRECTORY` writes UTF-8 JSONL run, attempt and score records plus cohort leaderboards. `--format json` writes one `runs.json` document containing the same records.

`results rescore RUN_ID --preflight REPORT --output FILE` reads saved completions, checks task coverage and prompt equality, and executes them in a newly validated Docker evaluator. It writes a separate JSON report with source run ID, original generation settings, new evaluator identity, each old/new outcome, confidence interval and an explicit zero count of new API requests. It never overwrites answers or invents a new generation score.

Historical exports retain their original schema and settings. They must be identified as historical; do not silently reinterpret their 3.10 environment, short hashes, costs or retries as protocol v2.

# Output Format Specification

This document describes the data storage format for benchmark results.

## SQLite Database

Results are stored in SQLite at `~/.graybench/results.db`.

### Schema Version

Current schema version: **1**

### Tables

#### `runs`

High-level metadata for each benchmark run.

| Column | Type | Description |
|--------|------|-------------|
| run_id | TEXT | Primary key (8-char UUID) |
| created_at | TEXT | ISO timestamp |
| suite | TEXT | "normal" or "hard" |
| provider | TEXT | Provider name |
| model | TEXT | Model ID |
| n_samples | INTEGER | Samples per task (default 1) |
| temperature | REAL | Sampling temperature |
| top_p | REAL | Nucleus sampling param |
| max_tokens | INTEGER | Max output tokens |
| timeout_seconds | INTEGER | Per-task timeout |
| dataset_version | TEXT | Dataset version string |
| dataset_hash | TEXT | Dataset content hash |
| environment_info | TEXT | JSON with env details |
| status | TEXT | "running" or "completed" |
| completed_at | TEXT | ISO timestamp |

#### `attempts`

Individual task attempt results.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment primary key |
| run_id | TEXT | Foreign key to runs |
| task_id | TEXT | Task identifier |
| sample_id | INTEGER | Sample index (0 for pass@1) |
| prompt | TEXT | Full prompt text |
| completion | TEXT | Model output |
| extracted_code | TEXT | Code extracted for execution |
| extraction_success | INTEGER | 0/1 boolean |
| outcome | TEXT | Outcome category |
| passed | INTEGER | 0/1 boolean |
| error_type | TEXT | Error class name |
| error_message | TEXT | Error description |
| stdout | TEXT | Captured stdout |
| stderr | TEXT | Captured stderr |
| generation_latency_ms | REAL | API call time |
| execution_time_ms | REAL | Test execution time |
| input_tokens | INTEGER | Prompt tokens |
| output_tokens | INTEGER | Completion tokens |
| total_tokens | INTEGER | Total tokens |
| cost_usd | REAL | Computed cost |
| raw_response | TEXT | Full API response JSON |
| created_at | TEXT | ISO timestamp |

#### `scores`

Aggregated scores per run.

| Column | Type | Description |
|--------|------|-------------|
| run_id | TEXT | Primary key, FK to runs |
| total_tasks | INTEGER | Number of tasks |
| passed | INTEGER | Tasks that passed |
| failed_test | INTEGER | Test assertion failures |
| failed_syntax | INTEGER | Syntax errors |
| failed_import | INTEGER | Import errors |
| failed_runtime | INTEGER | Runtime errors |
| timeouts | INTEGER | Timeout count |
| extraction_failed | INTEGER | Extraction failures |
| other_errors | INTEGER | Other errors |
| pass_rate | REAL | passed / total |
| total_input_tokens | INTEGER | Sum of input tokens |
| total_output_tokens | INTEGER | Sum of output tokens |
| total_cost_usd | REAL | Sum of costs |
| avg_generation_latency_ms | REAL | Mean generation time |
| avg_execution_time_ms | REAL | Mean execution time |

### Indexes

```sql
idx_attempts_run ON attempts (run_id)
idx_attempts_task ON attempts (task_id)
idx_attempts_outcome ON attempts (outcome)
idx_runs_provider ON runs (provider, model)
idx_runs_suite ON runs (suite)
```

## JSONL Export

Results can be exported to JSONL format for analysis and web integration.

### File Structure

```
exports/
├── {run_id}_run.jsonl        # Run metadata
├── {run_id}_attempts.jsonl   # All attempts
├── {run_id}_scores.jsonl     # Aggregated scores
├── leaderboard_normal.json   # Normal suite rankings
└── leaderboard_hard.json     # Hard suite rankings
```

### Run Metadata (JSONL)

```json
{
  "run_id": "abc12345",
  "created_at": "2026-01-15T10:30:00",
  "suite": "normal",
  "provider": "openai",
  "model": "gpt-4o",
  "n_samples": 1,
  "temperature": 0.0,
  "top_p": 1.0,
  "max_tokens": 4096,
  "timeout_seconds": 120,
  "dataset_version": "0.1.2",
  "dataset_hash": "a1b2c3d4e5f6",
  "environment_info": {"python_version": "3.10.12", ...},
  "status": "completed",
  "completed_at": "2026-01-15T10:45:00"
}
```

### Attempt Record (JSONL)

```json
{
  "run_id": "abc12345",
  "task_id": "qiskitHumanEval/42",
  "sample_id": 0,
  "prompt": "...",
  "completion": "...",
  "extracted_code": "def solution(): ...",
  "extraction_success": true,
  "outcome": "pass",
  "passed": true,
  "error_type": null,
  "error_message": null,
  "stdout": "ALL_TESTS_PASSED",
  "stderr": "",
  "generation_latency_ms": 1234.5,
  "execution_time_ms": 567.8,
  "input_tokens": 150,
  "output_tokens": 200,
  "total_tokens": 350,
  "cost_usd": 0.00123,
  "created_at": "2026-01-15T10:32:15"
}
```

### Scores Record (JSONL)

```json
{
  "run_id": "abc12345",
  "total_tasks": 151,
  "passed": 120,
  "failed_test": 15,
  "failed_syntax": 5,
  "failed_import": 3,
  "failed_runtime": 5,
  "timeouts": 2,
  "extraction_failed": 1,
  "other_errors": 0,
  "pass_rate": 0.7947,
  "total_input_tokens": 22650,
  "total_output_tokens": 30200,
  "total_cost_usd": 0.185,
  "avg_generation_latency_ms": 1150.3,
  "avg_execution_time_ms": 450.2
}
```

### Leaderboard (JSON)

```json
[
  {
    "provider": "openai",
    "model": "gpt-5.2-pro",
    "pass_rate": 0.8543,
    "total_tasks": 151,
    "passed": 129,
    "total_cost_usd": 0.523,
    "created_at": "2026-01-15T12:00:00",
    "run_id": "xyz98765"
  },
  {
    "provider": "anthropic",
    "model": "claude-4.5-opus-latest",
    "pass_rate": 0.8278,
    "total_tasks": 151,
    "passed": 125,
    "total_cost_usd": 0.312,
    "created_at": "2026-01-15T11:30:00",
    "run_id": "def45678"
  }
]
```

## Outcome Values

| Value | Description |
|-------|-------------|
| `pass` | All tests passed |
| `fail_test` | Test assertion failed |
| `fail_syntax` | Python syntax error |
| `fail_import` | Missing module/import |
| `fail_runtime` | Other runtime exception |
| `timeout` | Execution exceeded timeout |
| `extraction_failed` | Could not extract code |
| `error_other` | Unknown error |

## Querying Examples

### Get pass rate by model

```sql
SELECT r.provider, r.model, s.pass_rate
FROM runs r
JOIN scores s ON r.run_id = s.run_id
WHERE r.suite = 'normal'
ORDER BY s.pass_rate DESC;
```

### Get failure breakdown

```sql
SELECT outcome, COUNT(*) as count
FROM attempts
WHERE run_id = 'abc12345'
GROUP BY outcome;
```

### Get most expensive runs

```sql
SELECT run_id, provider, model, total_cost_usd
FROM runs r
JOIN scores s ON r.run_id = s.run_id
ORDER BY s.total_cost_usd DESC
LIMIT 10;
```

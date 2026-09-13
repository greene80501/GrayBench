"""Re-evaluate saved completions without generating replacements or overwriting runs."""

import json
from concurrent.futures import ThreadPoolExecutor

from graybench.dataset import DatasetLoader
from graybench.execution import ExecutionHarness, Outcome
from graybench.metrics import wilson_interval
from graybench.preflight import verify_report


def rescore_run(storage, run_id, preflight, workers=4):
    run = storage.get_run(run_id)
    if run is None:
        raise ValueError("Unknown source run")
    dataset = DatasetLoader().load(run["suite"])
    eligible = set(verify_report(preflight, dataset))
    if preflight.get("backend") != "docker":
        raise ValueError("Rescoring model output requires Docker")
    attempts = storage.get_attempts(run_id)
    if not attempts or len(attempts) != len({a["task_id"] for a in attempts}):
        raise ValueError("Source attempts are missing or duplicated")
    if any(a["outcome"] == "api_error" for a in attempts):
        raise ValueError("Source has operational API failures, not a valid model evaluation")
    by_id = {a["task_id"]: a for a in attempts}
    tasks = [task for task in dataset if task.task_id in eligible]
    if any(task.task_id not in by_id for task in tasks):
        raise ValueError("Source run does not cover all reference-validated tasks")
    if any(by_id[task.task_id]["prompt"] != task.prompt for task in tasks):
        raise ValueError("Source prompts differ from the current dataset")

    def evaluate(task):
        attempt = by_id[task.task_id]
        result = ExecutionHarness(
            timeout_seconds=preflight["timeout"], backend="docker", image=preflight["image"]
        ).execute(task, attempt["completion"])
        if not attempt["completion"].strip():
            result.outcome = Outcome.EMPTY_COMPLETION
        return {
            "task_id": task.task_id,
            "source_passed": bool(attempt["passed"]),
            "source_outcome": attempt["outcome"],
            **result.to_dict(),
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(evaluate, tasks))
    passed = sum(result["passed"] for result in results)
    low, high = wilson_interval(passed, len(results))
    return {
        "kind": "saved_completion_rescore",
        "source_run": run_id,
        "provider": run["provider"],
        "model": run["model"],
        "suite": run["suite"],
        "generation_created_at": run["created_at"],
        "generation_settings": {key: run[key] for key in ("temperature", "top_p", "max_tokens")},
        "source_manifest": json.loads(run["environment_info"]).get("manifest", {}),
        "preflight": preflight["fingerprint"],
        "evaluator": preflight["evaluator"],
        "image": preflight["image"],
        "dataset_hash": dataset.dataset_hash,
        "dataset_revision": dataset.version,
        "dataset_size": len(dataset),
        "task_ids": [task.task_id for task in tasks],
        "new_api_requests": 0,
        "new_api_cost_usd": 0,
        "passed": passed,
        "total_tasks": len(results),
        "pass_rate": passed / len(results),
        "wilson_95_low": low,
        "wilson_95_high": high,
        "results": results,
    }

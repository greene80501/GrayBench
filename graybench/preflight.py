"""Freeze task eligibility before seeing any model output."""

import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from graybench.execution import ExecutionHarness


def environment():
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "packages": dict(
            sorted(
                (d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions()
            )
        ),
    }


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def evaluator_fingerprint():
    root = Path(__file__).parent
    files = [root / "preflight.py", *sorted((root / "execution").glob("*.py"))]
    return fingerprint(
        {path.relative_to(root).as_posix(): path.read_text(encoding="utf-8") for path in files}
    )


def external_service(task):
    source = task.canonical_solution + "\n" + task.test
    # These are explicit service constructors in the pinned reference/tests.
    return any(
        name in source
        for name in (
            "QiskitRuntimeService(",
            "IBMProvider(",
            "TranspilerService(",
            "QiskitFunctionsCatalog(",
            ".save_account(",
        )
    )


def validate_dataset(
    dataset, workers=4, timeout=120, backend="local", image="graybench-evaluator:2.0"
):
    if backend == "docker":
        from graybench.execution.container import image_id

        image = image_id(image)

    def validate(task):
        if external_service(task):
            return {
                "task_id": task.task_id,
                "passed": False,
                "outcome": "requires_external_service",
                "error_message": "External-service credentials excluded from this offline profile",
            }
        try:
            result = ExecutionHarness(
                timeout_seconds=timeout, backend=backend, image=image
            ).validate_with_canonical(task)
            return {"task_id": task.task_id, **result.to_dict()}
        except Exception as error:
            return {
                "task_id": task.task_id,
                "passed": False,
                "outcome": "invalid_reference",
                "error_message": str(error),
            }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(validate, dataset.tasks))
    report = {
        "protocol": "graybench-v2",
        "suite": dataset.suite,
        "dataset_hash": dataset.dataset_hash,
        "dataset_revision": dataset.version,
        "environment": environment(),
        "evaluator": evaluator_fingerprint(),
        "timeout": timeout,
        "backend": backend,
        "image": image if backend == "docker" else None,
        "task_ids": [r["task_id"] for r in results if r["passed"]],
        "results": results,
    }
    report["fingerprint"] = fingerprint(report)
    return report


def verify_report(report, dataset):
    content = {k: v for k, v in report.items() if k != "fingerprint"}
    if report.get("fingerprint") != fingerprint(content):
        raise ValueError("Preflight report fingerprint mismatch")
    if report.get("dataset_hash") != dataset.dataset_hash or report.get("suite") != dataset.suite:
        raise ValueError("Preflight belongs to a different dataset or suite")
    if report.get("environment") != environment():
        raise ValueError("Environment changed since preflight; validate references again")
    if report.get("evaluator") != evaluator_fingerprint():
        raise ValueError("Evaluator changed since preflight; validate references again")
    if not report.get("task_ids"):
        raise ValueError("No validated tasks available")
    expected = [r["task_id"] for r in report.get("results", []) if r.get("passed") is True]
    all_ids = [r["task_id"] for r in report.get("results", [])]
    if all_ids != [task.task_id for task in dataset.tasks] or expected != report["task_ids"]:
        raise ValueError("Preflight task eligibility does not match reference results")
    return report["task_ids"]

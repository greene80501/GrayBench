"""Bind current native calibration logs to pinned answers and judge manifests.

This verifies local evidence consistency. It cannot attest independent Docker
execution, oracle adequacy, or resistance to same-process test inspection.
"""

import argparse
import json
from pathlib import Path

from graybench.datasets import EXTERNAL_IDS, load_suite
from graybench.identity import canonical, identity
from graybench.native_assembly import native_payload
from graybench.native_cohort import freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan

IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
EXTRACTION = {"normal": "exact_prompt_suffix_v1", "hard": "raw_or_single_python_fence_v1"}
PURPOSE = "reference interface calibration; not model scoring"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_scan(path: Path, cache: Path, *, suite: str) -> dict:
    """Recreate the exact 143-task cohort and compare every saved result."""
    require(suite in EXTRACTION, "Unknown native suite")
    inspected = inspect_reference_scan(path)
    require(inspected["complete"] and inspected["planned"] == 143, "Incomplete native scan")
    records = [json.loads(line)["event"] for line in path.read_bytes().splitlines()]
    header = records[0]
    source = source_manifest()
    require(
        header["source"] == source and header["purpose"] == PURPOSE, "Native scan source differs"
    )

    pinned = load_suite(suite, cache)
    tasks = tuple(
        task for task in pinned if int(task.public.task_id.rsplit("/", 1)[1]) not in EXTERNAL_IDS
    )
    excluded = {
        task_key(task): "external_service"
        for task in pinned
        if int(task.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
    }
    cohort = freeze_native_cohort(
        tasks,
        cache=cache,
        suite=suite,
        population="offline_143",
        image=IMAGE,
        extraction=EXTRACTION[suite],
        label="native reference calibration",
        excluded=excluded,
    )
    require(
        header["tasks"] == cohort.task_digests
        and header["selection"]
        == {
            "track": cohort.track,
            "cohort": cohort.model_dump(mode="json"),
            "cohort_digest": cohort.digest,
            "include_external": False,
        },
        "Native scan cohort differs from pinned tasks",
    )
    judge = NativeJudge(cohort, tasks, cache=cache)
    results = {event["task_key"]: event for event in records if event["kind"] == "result"}
    require(set(results) == set(cohort.task_keys), "Native scan results differ from cohort")
    for task in tasks:
        key = task_key(task)
        result = results[key]
        _, manifest = judge.configuration(task)
        payload = native_payload(task, task.canonical_solution, cohort.extraction)
        require("extraction_error" not in payload, f"Canonical answer extraction failed: {key}")
        evidence = result["evidence"]
        require(
            result["judge_digest"] == identity(manifest) and evidence["manifest"] == manifest,
            f"Native judge identity differs: {key}",
        )
        require(
            all(
                evidence.get(name) == payload[name]
                for name in ("completion_sha256", "code_sha256", "extraction_method")
            ),
            f"Native canonical answer differs: {key}",
        )
        worker_result = evidence.get("worker_result")
        artifact = evidence.get("result_artifact")
        require(
            result["outcome"] == "pass"
            and worker_result == {"completed": True, "phase": "test", "status": "pass"}
            and artifact
            == {
                "capture": "isolated-ephemeral-host-bind-v1",
                "name": "result.json",
                "sha256": identity(worker_result),
                "size": len(canonical(worker_result)),
            },
            f"Native canonical result differs: {key}",
        )
    return {
        "suite": suite,
        "planned": len(tasks),
        "canonical_passes": sum(result["outcome"] == "pass" for result in results.values()),
        "complete": True,
        "cohort_digest": cohort.digest,
        "source_digest": source["digest"],
        "image": IMAGE,
        "extraction": cohort.extraction,
        "file_sha256": inspected["file_sha256"],
        "chain_head": inspected["chain_head"],
        "publication_eligible": False,
    }


def verify_pair(directory: Path, cache: Path) -> list[dict]:
    return [
        verify_scan(directory / f"{suite}.jsonl", cache, suite=suite)
        for suite in ("normal", "hard")
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_pair(args.directory, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

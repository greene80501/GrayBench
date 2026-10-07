"""Screen two trivial literal returns against every pinned offline native test.

This records candidate controls under the same native cohorts as the current
canonical calibration. A survivor requires public-contract review before it
can be called a false pass. This is never a model score or task admission.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from graybench.datasets import EXTERNAL_IDS, load_suite
from graybench.identity import canonical, identity
from graybench.native_assembly import native_payload
from graybench.native_cohort import freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan, run_evidence_cases

IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
EXTRACTION = {"normal": "exact_prompt_suffix_v1", "hard": "raw_or_single_python_fence_v1"}
LITERALS = {"zero": "0", "empty_list": "[]"}
PURPOSE = "native literal-mutant oracle screen; not model scoring or task admission"


def completion(task, literal: str) -> str:
    if task.public.suite == "normal":
        return f"\n    return {literal}\n"
    return f"def {task.public.entry_point}(*args, **kwargs):\n    return {literal}\n"


def plan(cache: Path) -> tuple[list[tuple], dict, dict]:
    cases = []
    judges = {}
    cohorts = {}
    for suite in ("normal", "hard"):
        pinned = load_suite(suite, cache)
        tasks = tuple(
            task
            for task in pinned
            if int(task.public.task_id.rsplit("/", 1)[1]) not in EXTERNAL_IDS
        )
        cohort = freeze_native_cohort(
            tasks,
            cache=cache,
            suite=suite,
            population="offline_143",
            image=IMAGE,
            extraction=EXTRACTION[suite],
            label="native reference calibration",
            excluded={
                task_key(task): "external_service"
                for task in pinned
                if int(task.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
            },
        )
        cohorts[suite] = cohort
        judges[suite] = NativeJudge(cohort, tasks, cache=cache)
        for task in tasks:
            for mutant, literal in LITERALS.items():
                cases.append(
                    (
                        f"{task_key(task)}/{mutant}",
                        task.digest,
                        (task, completion(task, literal)),
                    )
                )
    return cases, judges, cohorts


def selection(cohorts: dict) -> dict:
    return {
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "image": IMAGE,
        "mutants": LITERALS,
        "cohorts": {suite: cohort.model_dump(mode="json") for suite, cohort in cohorts.items()},
        "cohort_digests": {suite: cohort.digest for suite, cohort in cohorts.items()},
    }


def run(cache: Path, output: Path) -> dict:
    cases, judges, cohorts = plan(cache)
    result = run_evidence_cases(
        cases,
        lambda case: judges[case[0].public.suite].evaluate(*case),
        output,
        purpose=PURPOSE,
        selection=selection(cohorts),
    )
    return {
        "complete": result["complete"],
        "planned": result["planned"],
        "outcomes": dict(Counter(result["results"].values())),
        "passes": sorted(key for key, value in result["results"].items() if value == "pass"),
        "file_sha256": result["file_sha256"],
        "chain_head": result["chain_head"],
    }


def verify(cache: Path, path: Path) -> dict:
    """Recreate task, mutant, cohort, answer-hash and judge bindings."""
    inspected = inspect_reference_scan(path)
    if not inspected["complete"] or inspected["planned"] != 572:
        raise ValueError("Incomplete native literal-mutant screen")
    records = [json.loads(line)["event"] for line in path.read_bytes().splitlines()]
    cases, judges, cohorts = plan(cache)
    header = records[0]
    if (
        header["source"] != source_manifest()
        or header["purpose"] != PURPOSE
        or header["selection"] != selection(cohorts)
        or header["tasks"] != {key: digest for key, digest, _ in cases}
    ):
        raise ValueError("Native literal-mutant screen differs from frozen plan")
    results = {event["task_key"]: event for event in records if event["kind"] == "result"}
    if set(results) != {key for key, _, _ in cases}:
        raise ValueError("Native literal-mutant result set differs from frozen plan")
    for key, _, (task, answer) in cases:
        result = results[key]
        _, manifest = judges[task.public.suite].configuration(task)
        payload = native_payload(task, answer, cohorts[task.public.suite].extraction)
        evidence = result["evidence"]
        if (
            "extraction_error" in payload
            or result["judge_digest"] != identity(manifest)
            or evidence.get("manifest") != manifest
            or any(
                evidence.get(field) != payload[field]
                for field in ("completion_sha256", "code_sha256", "extraction_method")
            )
        ):
            raise ValueError(f"Native literal-mutant answer or judge differs: {key}")
        worker = evidence.get("worker_result")
        artifact = evidence.get("result_artifact")
        if worker is not None and artifact != {
            "capture": "isolated-ephemeral-host-bind-v1",
            "name": "result.json",
            "sha256": identity(worker),
            "size": len(canonical(worker)),
        }:
            raise ValueError(f"Native literal-mutant worker artifact differs: {key}")
        worker_pass = worker == {
            "completed": True,
            "phase": "test",
            "status": "pass",
        }
        if (result["outcome"] == "pass") != worker_pass:
            raise ValueError(f"Native literal-mutant pass differs from worker: {key}")
    counts = Counter(result["outcome"] for result in results.values())
    return {
        "complete": True,
        "planned": len(cases),
        "source_digest": source_manifest()["digest"],
        "image": IMAGE,
        "cohort_digests": {suite: cohort.digest for suite, cohort in cohorts.items()},
        "outcomes": dict(counts),
        "passes": sorted(key for key, value in results.items() if value["outcome"] == "pass"),
        "file_sha256": inspected["file_sha256"],
        "chain_head": inspected["chain_head"],
        "publication_eligible": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "verify"))
    parser.add_argument("cache", type=Path)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.cache, args.path) if args.mode == "run" else verify(args.cache, args.path)
        )
    )


if __name__ == "__main__":
    main()

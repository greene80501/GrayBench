"""Check byte-pinned native reference spot-check logs and their event chains."""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.native_cohort import NativeCohort, task_key, validate_native_cohort
from graybench.native_judge import NativeJudge
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan

HERE = Path(__file__).resolve().parent
COHORT_DIGESTS = {
    "normal": "6071babe00ee8f15a97cea24243e3fd4c15e7050e9ff3dbe6180ad1b8436eea5",
    "hard": "d669dd2ac4bf95a754d822a19fdb994c9d2564a373162786ef606842853ab215",
}
EXTRACTIONS = {
    "normal": "exact_prompt_suffix_v1",
    "hard": "raw_or_single_python_fence_v1",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="Local SHA-256-pinned QHE dataset cache")
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.json").read_bytes())
    require(manifest["schema_version"] == "1", "Unexpected manifest schema")
    require(
        manifest["source_revision"] == "2e9854d4063291198e4aa5b6dc778418ec2258f4",
        "Unexpected source revision",
    )
    require(manifest["task_ids"] == [62, 63, 100, 109], "Unexpected task selection")
    require(manifest["repeats_per_suite"] == 3, "Unexpected repeat count")
    names = {f"{suite}-repeat-{repeat}.jsonl" for suite in COHORT_DIGESTS for repeat in range(1, 4)}
    entries = manifest["files"]
    require(
        len(entries) == 6 and {item["path"] for item in entries} == names,
        "Manifest file set differs",
    )
    require({path.name for path in HERE.glob("*.jsonl")} == names, "Bundle file set differs")
    for item in entries:
        path = HERE / item["path"]
        raw = path.read_bytes()
        require(len(raw) == item["bytes"], f"Byte count differs: {path.name}")
        require(hashlib.sha256(raw).hexdigest() == item["sha256"], f"SHA-256 differs: {path.name}")
        suite = path.name.split("-", 1)[0]
        expected_tasks = {f"{suite}/qiskitHumanEval/{number}" for number in manifest["task_ids"]}
        inspected = inspect_reference_scan(path)
        require(
            inspected["complete"] and inspected["pending_task"] is None,
            f"Incomplete chain: {path.name}",
        )
        require(inspected["file_sha256"] == item["sha256"], f"Inspector hash differs: {path.name}")
        require(
            inspected["purpose"] == "reference interface calibration; not model scoring",
            f"Wrong purpose: {path.name}",
        )
        require(
            inspected["planned"] == 4 and set(inspected["results"]) == expected_tasks,
            f"Wrong tasks: {path.name}",
        )
        require(
            all(outcome == "pass" for outcome in inspected["results"].values()),
            f"Canonical failure: {path.name}",
        )
        header = json.loads(raw.splitlines()[0])["event"]
        selection = header["selection"]
        source = header["source"]
        require(identity(source["files"]) == source["digest"], f"Source hash differs: {path.name}")
        require(source == source_manifest(), f"Current engine source differs: {path.name}")
        cohort = NativeCohort.model_validate_json(json.dumps(selection["cohort"]))
        tasks = tuple(
            task for task in load_suite(suite, args.cache) if task_key(task) in expected_tasks
        )
        validate_native_cohort(cohort, tasks, cache=args.cache)
        judge = NativeJudge(cohort, tasks, cache=args.cache)
        require(source["digest"] == manifest["source_digest"], f"Source differs: {path.name}")
        require(
            selection["cohort_digest"] == COHORT_DIGESTS[suite] == cohort.digest,
            f"Cohort differs: {path.name}",
        )
        require(
            cohort.suite == suite and cohort.track == "qhe-pinned-native-v1",
            f"Track differs: {path.name}",
        )
        require(
            cohort.image == manifest["image"] and cohort.extraction == EXTRACTIONS[suite],
            f"Runtime differs: {path.name}",
        )
        require(
            cohort.population == "custom_development" and set(cohort.task_keys) == expected_tasks,
            f"Selection differs: {path.name}",
        )
        require(header["tasks"] == cohort.task_digests, f"Task ancestry differs: {path.name}")
        task_by_key = {task_key(task): task for task in tasks}
        for line in raw.splitlines()[1:]:
            event = json.loads(line)["event"]
            if event["kind"] != "result":
                continue
            key = event["task_key"]
            _, expected_manifest = judge.configuration(task_by_key[key])
            require(
                event["evidence"]["manifest"] == expected_manifest
                and event["judge_digest"] == identity(expected_manifest),
                f"Result judge manifest differs: {path.name}/{key}",
            )
        print(f"{path.name}: four canonical passes; chain and source-bound selection verified")


if __name__ == "__main__":
    main()

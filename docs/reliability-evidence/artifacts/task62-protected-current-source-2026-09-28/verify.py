"""Verify the source-bound, development-only protected task-62 control bundle."""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.oracle_review import inspect_oracle_review
from graybench.protected_oracle_review import protected_probes
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task62 import TASK62_SOURCE_DIGESTS, task62_value_task
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest

HERE = Path(__file__).resolve().parent
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
SOURCE_DIGEST = "bcd6b4379ee62c3c8a15be4d6368e961467ab7506d6787a39ede36d60782a70d"
LOG_SHA256 = "902fd1fe09c2cd54cca73845687be90513b82ae0845f879e63d7633dd0291292"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path, help="Local SHA-256-pinned QHE dataset cache")
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.json").read_bytes())
    require(manifest["schema_version"] == "1", "Unexpected manifest schema")
    require(manifest["source_digest"] == SOURCE_DIGEST, "Unexpected source digest")
    require(manifest["image"] == IMAGE, "Unexpected runtime image")
    require(
        manifest["log"] == {"path": "control.jsonl", "bytes": 282649, "sha256": LOG_SHA256},
        "Unexpected log identity",
    )
    raw = (HERE / "control.jsonl").read_bytes()
    require(len(raw) == manifest["log"]["bytes"], "Log byte length differs")
    require(hashlib.sha256(raw).hexdigest() == LOG_SHA256, "Log SHA-256 differs")

    inspected = inspect_oracle_review(HERE / "control.jsonl", args.cache)
    require(inspected["file_sha256"] == LOG_SHA256, "Inspected log SHA-256 differs")
    require(inspected["source_digest"] == SOURCE_DIGEST, "Logged engine digest differs")
    require(
        inspected["locally_verified"]
        and not inspected["publication_eligible"]
        and inspected["control_count"] == inspected["controls_matching_expectation"] == 16
        and inspected["expected_passes"] == 6
        and inspected["expected_failures"] == 10
        and not inspected["unexpected_outcomes"],
        "Control outcomes differ",
    )
    require(
        set(inspected["task_keys"]) == {"normal/qiskitHumanEval/62", "hard/qiskitHumanEval/62"},
        "Unexpected controlled tasks",
    )
    require(source_manifest()["digest"] == SOURCE_DIGEST, "Current engine source differs")

    events = [json.loads(line)["event"] for line in raw.splitlines()]
    header = events[0]
    require(
        header["kind"] == "header" and header["source"] == source_manifest(),
        "Header source differs",
    )
    selection = header["selection"]
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE))
    expected_cases = {}
    expected_judges = {}
    for suite in ("normal", "hard"):
        source = load_suite(suite, args.cache)[62]
        require(source.digest == TASK62_SOURCE_DIGESTS[suite], "Pinned task-62 source differs")
        revision = task62_value_task(source)
        key = f"{suite}/qiskitHumanEval/62"
        expected_judges[key] = judge.manifest(revision)
        for probe in protected_probes(source):
            expected_cases[f"{key}/{probe.name}"] = {
                "task_digest": source.digest,
                "expectation": probe.expectation,
                "rationale": probe.rationale,
                "completion": probe.completion,
            }
    require(selection["declared_judges"] == expected_judges, "Predeclared current judges differ")
    require(selection["cases"] == expected_cases, "Predeclared probes differ")
    require(
        header["tasks"] == {key: identity(case) for key, case in expected_cases.items()},
        "Case digests differ",
    )
    require(
        all(
            control["judge_predeclared"] and control["judge_manifest_verified"]
            for control in inspected["controls"]
        ),
        "A control lacks a verified predeclared judge",
    )
    print("Protected task-62 controls verified: 16/16 expected; publication ineligible")


if __name__ == "__main__":
    main()

"""Verify the source-bound protected task-62 exhaustive-v2 control bundle."""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.oracle_review import inspect_oracle_review
from graybench.protected_oracle_review import protected_probes
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task62 import TASK62_SOURCE_DIGESTS, task62_value_task_v2
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest

HERE = Path(__file__).resolve().parent
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
SOURCE_DIGEST = "669b151ec3560455d6ffee16adf9706d2cf4b898cc86fe94517e1561317b8289"
LOG_SHA256 = "2e29910a57d907e0b6e4e7ceda3067ea04587e01a8858be3368698fbffa15ce0"
LOG_BYTES = 2681337


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
        manifest["log"] == {"path": "control.jsonl", "bytes": LOG_BYTES, "sha256": LOG_SHA256},
        "Unexpected log identity",
    )
    raw = (HERE / "control.jsonl").read_bytes()
    require(len(raw) == LOG_BYTES, "Log byte length differs")
    require(hashlib.sha256(raw).hexdigest() == LOG_SHA256, "Log SHA-256 differs")
    report = inspect_oracle_review(HERE / "control.jsonl", args.cache)
    require(report["file_sha256"] == LOG_SHA256, "Inspected log SHA-256 differs")
    require(report["source_digest"] == SOURCE_DIGEST, "Logged source digest differs")
    require(
        report["locally_verified"]
        and not report["publication_eligible"]
        and report["control_count"] == report["controls_matching_expectation"] == 18
        and report["expected_passes"] == 6
        and report["expected_failures"] == 12
        and not report["unexpected_outcomes"],
        "Control outcomes differ",
    )
    require(source_manifest()["digest"] == SOURCE_DIGEST, "Current engine source differs")
    events = [json.loads(line)["event"] for line in raw.splitlines()]
    header = events[0]
    require(
        header["kind"] == "header" and header["source"] == source_manifest(),
        "Header source differs",
    )
    selection = header["selection"]
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=120.0))
    expected_cases = {}
    expected_judges = {}
    for suite in ("normal", "hard"):
        source = load_suite(suite, args.cache)[62]
        require(source.digest == TASK62_SOURCE_DIGESTS[suite], "Pinned task-62 source differs")
        revision = task62_value_task_v2(source)
        key = f"{suite}/qiskitHumanEval/62"
        require(len(revision.cases) == 1364, "V2 input domain differs")
        expected_judges[key] = judge.manifest(revision)
        for probe in protected_probes(source, oracle=revision.oracle):
            expected_cases[f"{key}/{probe.name}"] = {
                "task_digest": source.digest,
                "expectation": probe.expectation,
                "rationale": probe.rationale,
                "completion": probe.completion,
            }
    require(
        identity(selection["declared_judges"]) == identity(expected_judges),
        "Predeclared judges differ",
    )
    require(selection["cases"] == expected_cases, "Predeclared controls differ")
    require(
        header["tasks"] == {key: identity(case) for key, case in expected_cases.items()},
        "Control identities differ",
    )
    require(
        all(
            control["judge_predeclared"] and control["judge_manifest_verified"]
            for control in report["controls"]
        ),
        "A control lacks a verified predeclared judge",
    )
    omitted = [
        control
        for control in report["controls"]
        if control["case_key"].endswith("/omitted-input-bb84")
    ]
    require(
        len(omitted) == 2 and all(c["expected"] == c["actual"] == "fail" for c in omitted),
        "The v1 counterexample was not rejected in both suites",
    )
    omitted_events = [
        event
        for event in events
        if event["kind"] == "result" and event["task_key"].endswith("/omitted-input-bb84")
    ]
    require(len(omitted_events) == 2, "Missing exact omitted-input results")
    for event in omitted_events:
        cases = event["evidence"]["judgment"]["case_results"]
        require(len(cases) == 1364, "Omitted-input mutant did not run all v2 cases")
        require(
            [case["case_id"] for case in cases if not case["passed"]]
            == ["width-4-state-1000-basis-0000"],
            "Omitted-input mutant failed at a different v2 case",
        )
    print("Protected task-62 exhaustive-v2 controls verified: 18/18; publication ineligible")


if __name__ == "__main__":
    main()

"""Verify the frozen task-149 control plan and, optionally, its result log."""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from graybench.fs_paths import readable_path
from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan

HERE = Path(__file__).resolve().parent
PLAN_SHA256 = "111e5362ed7e7b1dc4636d03c7e73c50fc3ae836a69d96bcc04e886969982f50"
PROBE_SHA256 = "2af3ccb9d75373b8f34de2fbd089b505908a9e26c0e53fe5596453dd4f017784"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
RECIPE = "qhe149-most-common-bitstring-v1"
PURPOSE = "Task 149 protected authored controls; not model scoring"
PINNED_SOURCE_TASK_DIGESTS = {
    "normal": "363fe9e4032fcc9e3f16d0b38d41a9a7233dcee7c31728efc1f566cafc2bd013",
    "hard": "8071f037bf801abf0d2f16851d538e5656baadd6cda5a19fa69cd6eba17096bf",
}
CONTROL_EXPECTED = {
    "reference": "pass",
    "count-based": "pass",
    "first-string": "fail",
    "last-string": "fail",
    "fixed-string": "fail",
    "wrong-type": "fail",
    "candidate-exception": "candidate_error",
}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate task-149 control JSON key")
        result[key] = value
    return result


def read_plan(bundle: Path) -> dict:
    path = readable_path(bundle) / "plan.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked control plan")
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024 or hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("Control plan byte count or digest mismatch")
    return json.loads(raw, object_pairs_hook=unique_pairs)


def verify(bundle: Path = HERE) -> dict:
    plan = read_plan(bundle)
    probe = HERE.parents[1] / "task149_batch_probe.py"
    if (
        probe.is_symlink()
        or not probe.is_file()
        or hashlib.sha256(probe.read_bytes()).hexdigest() != PROBE_SHA256
    ):
        raise ValueError("Predeclared task-149 probe byte digest mismatch")
    if (
        type(plan) is not dict
        or set(plan) != {"cases", "declared_judges", "image", "probe_sha256", "recipe"}
        or plan["recipe"] != RECIPE
        or plan["image"] != IMAGE
        or plan["probe_sha256"] != PROBE_SHA256
    ):
        raise ValueError("Unexpected task-149 control plan")
    declared = plan["declared_judges"]
    judge_keys = {f"{suite}/qiskitHumanEval/149" for suite in ("normal", "hard")}
    if type(declared) is not dict or set(declared) != judge_keys:
        raise ValueError("Incomplete task-149 judge roster")
    expected = {
        f"{suite}/149/{control}": outcome
        for suite in ("normal", "hard")
        for control, outcome in CONTROL_EXPECTED.items()
    }
    cases = plan["cases"]
    if type(cases) is not dict or set(cases) != set(expected):
        raise ValueError("Incomplete task-149 control roster")
    source = None
    for suite in ("normal", "hard"):
        judge = declared[f"{suite}/qiskitHumanEval/149"]
        inner = judge["inner"]
        current_source = judge["source"]
        if (
            judge["track"] != RECIPE
            or judge["release_eligible"] is not False
            or judge["pinned_source_task_digest"] != PINNED_SOURCE_TASK_DIGESTS[suite]
            or type(current_source) is not dict
            or set(current_source) != {"files", "digest"}
            or type(current_source["files"]) is not dict
            or not current_source["files"]
            or identity(current_source["files"]) != current_source["digest"]
            or inner["image"] != IMAGE
            or inner["protocol"] != "upstream-proxy-v1"
            or inner["candidate_timeout"] != 120
            or inner["judge_timeout"] != 120
        ):
            raise ValueError("Declared task-149 judge differs from frozen condition")
        if source is not None and current_source != source:
            raise ValueError("Normal and hard judges used different engine sources")
        source = current_source
    for key, outcome in expected.items():
        record = cases[key]
        suite = key.split("/", 1)[0]
        judge = declared[f"{suite}/qiskitHumanEval/149"]
        if (
            type(record) is not dict
            or set(record)
            != {
                "completion_sha256",
                "expected",
                "original_task_digest",
                "revised_public_digest",
                "revised_task_digest",
            }
            or record["expected"] != outcome
            or record["original_task_digest"] != PINNED_SOURCE_TASK_DIGESTS[suite]
            or record["revised_task_digest"] != judge["task_digest"]
            or record["revised_public_digest"] != judge["public_task_digest"]
            or re.fullmatch(r"[0-9a-f]{64}", record["completion_sha256"]) is None
        ):
            raise ValueError(f"Task-149 control identity differs: {key}")
    return {
        "predeclared": True,
        "controls_executed": False,
        "control_count": len(cases),
        "expected_outcomes": dict(Counter(expected.values())),
        "plan_sha256": PLAN_SHA256,
        "source_digest": source["digest"],
        "source_matches_running_source": source == source_manifest(),
        "publication_eligible": False,
    }


def verify_results(path: Path, bundle: Path = HERE) -> dict:
    """Check a log's internal bindings; this is not execution attestation."""
    plan_report = verify(bundle)
    plan = read_plan(bundle)
    path = readable_path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked task-149 result log")
    summary = inspect_reference_scan(path)
    cases = plan["cases"]
    if (
        not summary["complete"]
        or summary["planned"] != len(cases)
        or set(summary["results"]) != set(cases)
    ):
        raise ValueError("Incomplete task-149 control result roster")
    byte_count = 0
    file_digest = hashlib.sha256()
    seen = set()
    with path.open("rb") as stream:
        for index, raw in enumerate(stream, 1):
            byte_count += len(raw)
            if byte_count > 512 * 1024 * 1024 or len(raw) > 32 * 1024 * 1024:
                raise ValueError("Task-149 control result log exceeds byte limit")
            file_digest.update(raw)
            event = json.loads(raw, object_pairs_hook=unique_pairs)["event"]
            if index == 1:
                source = next(iter(plan["declared_judges"].values()))["source"]
                if (
                    event["kind"] != "header"
                    or event["purpose"] != PURPOSE
                    or event["source"] != source
                    or event["selection"] != plan
                    or event["tasks"] != {key: identity(case) for key, case in cases.items()}
                ):
                    raise ValueError("Task-149 result header differs from plan")
            if event["kind"] != "result":
                continue
            key = event["task_key"]
            if key not in cases or key in seen:
                raise ValueError("Task-149 result roster identity differs")
            seen.add(key)
            case = cases[key]
            suite = key.split("/", 1)[0]
            manifest = plan["declared_judges"][f"{suite}/qiskitHumanEval/149"]
            evidence = event["evidence"]
            judgment = evidence["judgment"]
            inner = judgment["inner"]
            if (
                event["outcome"] != case["expected"]
                or evidence["expected"] != case["expected"]
                or evidence["matches_expectation"] is not True
                or event["judge_digest"] != identity(manifest)
                or judgment["manifest"] != manifest
                or inner["manifest"] != manifest["inner"]
                or inner["public_task_digest"] != case["revised_public_digest"]
                or inner["completion_sha256"] != case["completion_sha256"]
            ):
                raise ValueError(f"Task-149 result differs from plan: {key}")
    if seen != set(cases) or file_digest.hexdigest() != summary["file_sha256"]:
        raise ValueError("Task-149 result roster or bytes changed during inspection")
    return {
        "plan_sha256": plan_report["plan_sha256"],
        "result_sha256": summary["file_sha256"],
        "chain_head": summary["chain_head"],
        "recorded_controls": len(seen),
        "results": dict(Counter(summary["results"].values())),
        "source_matches_running_source": plan_report["source_matches_running_source"],
        "execution_independently_attested": False,
        "publication_eligible": False,
    }


if __name__ == "__main__":
    if len(sys.argv) > 3:
        raise SystemExit("Usage: verify.py [BUNDLE_DIRECTORY [RESULT_LOG]]")
    bundle = Path(sys.argv[1]) if len(sys.argv) >= 2 else HERE
    report = verify_results(Path(sys.argv[2]), bundle) if len(sys.argv) == 3 else verify(bundle)
    print(json.dumps(report, sort_keys=True))

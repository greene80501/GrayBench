"""Verify the frozen task-63 batch control plan without claiming executions."""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from graybench.bb84_revision import PINNED_SOURCE_TASK_DIGESTS
from graybench.fs_paths import readable_path
from graybench.identity import identity
from graybench.provenance import source_manifest

HERE = Path(__file__).resolve().parent
PLAN_SHA256 = "04d67f997a637cebe8376e13294dcf4c85e50825e4f84e261476406a821b6055"
PROBE_SHA256 = "49a371264288177579212688b7db3b706c545fa6ca11a3f90e648ca6d5969040"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
RECIPE = "qhe63-explicit-bases-v2"
CONTROL_EXPECTED = {
    "simulator-reference": "pass",
    "statevector-copy": "pass",
    "statevector-in-place": "pass",
    "fixed-one": "fail",
    "basis-only": "fail",
    "no-sifting": "fail",
    "reverse-order": "fail",
    "candidate-exception": "candidate_error",
}


def unique_pairs(pairs):
    record = {}
    for key, value in pairs:
        if key in record:
            raise ValueError("Duplicate control plan JSON key")
        record[key] = value
    return record


def read_plan(path: Path) -> dict:
    path = readable_path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked control plan")
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise ValueError("Control plan exceeds byte limit")
    return json.loads(raw, object_pairs_hook=unique_pairs)


def verify(bundle: Path = HERE) -> dict:
    bundle = readable_path(bundle)
    path = bundle / "plan.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked control plan")
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024 or hashlib.sha256(raw).hexdigest() != PLAN_SHA256:
        raise ValueError("Control plan byte count or digest mismatch")
    plan = json.loads(raw, object_pairs_hook=unique_pairs)
    probe = HERE.parents[1] / "task63_batch_probe.py"
    if (
        probe.is_symlink()
        or not probe.is_file()
        or hashlib.sha256(probe.read_bytes()).hexdigest() != PROBE_SHA256
    ):
        raise ValueError("Predeclared probe byte digest mismatch")
    if (
        type(plan) is not dict
        or set(plan) != {"cases", "declared_judges", "image", "probe_sha256", "recipe"}
        or plan["recipe"] != RECIPE
        or plan["image"] != IMAGE
        or plan["probe_sha256"] != PROBE_SHA256
    ):
        raise ValueError("Unexpected task-63 batch control plan")
    declared = plan["declared_judges"]
    expected_judge_keys = {f"{suite}/qiskitHumanEval/63" for suite in ("normal", "hard")}
    if type(declared) is not dict or set(declared) != expected_judge_keys:
        raise ValueError("Incomplete declared judge roster")
    expected_keys = {
        f"{suite}/63/{control}": outcome
        for suite in ("normal", "hard")
        for control, outcome in CONTROL_EXPECTED.items()
    }
    cases = plan["cases"]
    if type(cases) is not dict or set(cases) != set(expected_keys):
        raise ValueError("Incomplete declared control roster")
    source = None
    for suite in ("normal", "hard"):
        judge = declared[f"{suite}/qiskitHumanEval/63"]
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
            or inner["protocol"] != "upstream-graph-v4"
            or inner["graph_batch"] != "positional-batch-v1"
            or inner["batch_case_limit"] != 1024
            or inner["graph_transport"]
            != {"mode": "delta-v1", "state_bytes": 16 * 1024 * 1024, "wire_bytes": 16 * 1024 * 1024}
            or inner["graph_limits"]["message_bytes"] != 16 * 1024 * 1024
            or inner["output_limit"] != 16 * 1024 * 1024
            or inner["candidate_timeout"] != 120
            or inner["judge_timeout"] != 120
        ):
            raise ValueError("Declared batch judge differs from the frozen condition")
        if source is not None and current_source != source:
            raise ValueError("Normal and hard judges used different engine sources")
        source = current_source
    for key, outcome in expected_keys.items():
        record = cases[key]
        suite = key.split("/", 1)[0]
        judge = declared[f"{suite}/qiskitHumanEval/63"]
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
            raise ValueError(f"Control identity or outcome differs: {key}")
    return {
        "predeclared": True,
        "controls_executed": False,
        "control_count": len(cases),
        "expected_outcomes": dict(Counter(expected_keys.values())),
        "plan_sha256": PLAN_SHA256,
        "source_digest": source["digest"],
        "source_matches_running_source": source == source_manifest(),
        "publication_eligible": False,
    }


if __name__ == "__main__":
    if len(sys.argv) > 2:
        raise SystemExit("Usage: verify.py [BUNDLE_DIRECTORY]")
    print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv) == 2 else HERE), sort_keys=True))

"""Carry task-62 admission evidence to the current engine source without rewriting history."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from graybench.admission_bundle import verify_admission_bundle
from graybench.identity import canonical
from graybench.oracle_review import inspect_oracle_review
from graybench.provenance import source_manifest
from graybench.task_admission import (
    AdmissionInventory,
    audit_control_coverage,
    require_current_finding_registry,
    validate_inventory,
)

HERE = Path(__file__).resolve().parent
PREDECESSOR = HERE / "artifacts/admission-task62-protected-2026-09-28"
CURRENT = HERE / "artifacts/task62-protected-current-source-2026-09-28"
OLD_REVIEW_NAME = "GrayBench-v3-task62-protected-controls-both-20260928.jsonl"
NEW_REVIEW_NAME = "task62-current-source.jsonl"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def descriptor(name: str, data: bytes) -> dict:
    return {"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read_pinned(path: Path, record: dict) -> bytes:
    data = path.read_bytes()
    require(
        len(data) == record["bytes"] and hashlib.sha256(data).hexdigest() == record["sha256"],
        f"Pinned artifact differs: {path}",
    )
    return data


def stable_events(data: bytes) -> list[dict]:
    return [
        {
            key: value
            for key, value in json.loads(line)["event"].items()
            if key not in {"at", "created_at", "source"}
        }
        for line in data.splitlines()
    ]


def build(cache: Path, output: Path) -> dict:
    require(not output.exists(), "Output bundle already exists")
    require(verify_admission_bundle(PREDECESSOR, cache)["verified"], "Predecessor failed")
    previous_manifest = json.loads((PREDECESSOR / "manifest.json").read_bytes())
    previous_inventory = AdmissionInventory.model_validate_json(
        read_pinned(
            PREDECESSOR / previous_manifest["inventory"]["file"],
            previous_manifest["inventory"],
        )
    )
    require_current_finding_registry(previous_inventory)
    source = source_manifest()["digest"]
    require(previous_inventory.source_digest != source, "Predecessor already uses current source")

    current_manifest = json.loads((CURRENT / "manifest.json").read_bytes())
    require(current_manifest["source_digest"] == source, "Current control source differs")
    current_data = read_pinned(CURRENT / current_manifest["log"]["path"], current_manifest["log"])
    require(
        json.loads(current_data.splitlines()[0])["event"]["source"] == source_manifest(),
        "Current control header source differs",
    )
    current_report = inspect_oracle_review(CURRENT / current_manifest["log"]["path"], cache)
    require(
        current_report["locally_verified"]
        and current_report["source_digest"] == source
        and current_report["control_count"] == current_report["controls_matching_expectation"] == 16
        and current_report["expected_passes"] == 6
        and current_report["expected_failures"] == 10
        and not current_report["publication_eligible"]
        and not current_report["unexpected_outcomes"],
        "Current task-62 controls differ",
    )

    reviews = {}
    old_review_data = None
    for record in previous_manifest["reviews"]:
        name = record["file"]
        data = read_pinned(PREDECESSOR / name, record)
        if name == OLD_REVIEW_NAME:
            require(old_review_data is None, "Duplicate old task-62 log")
            old_review_data = data
            reviews[NEW_REVIEW_NAME] = current_data
        else:
            reviews[name] = data
    require(old_review_data is not None, "Missing old task-62 log")
    require(
        stable_events(old_review_data) == stable_events(current_data),
        "Task-62 declarations or results changed while refreshing source",
    )
    require(len(reviews) == len(previous_manifest["reviews"]), "Review count changed")

    inventory = previous_inventory.model_copy(update={"source_digest": source})
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    inventory_bytes = canonical(inventory.model_dump(mode="json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gb-adm-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        (staging / "inventory.json").write_bytes(inventory_bytes)
        for name, data in reviews.items():
            (staging / name).write_bytes(data)
        audit = audit_control_coverage(inventory, cache, tuple(staging / name for name in reviews))
        require(
            audit["control_count"] == 58
            and audit["covered_task_count"] == 10
            and audit["uncovered_task_count"] == 292
            and audit["declared_frozen_judge_control_count"] == 40
            and audit["false_pass_count"] == 8
            and not audit["publication_eligible"],
            "Refreshed audit differs from expected coverage",
        )
        audit_bytes = canonical(audit)
        (staging / "audit.json").write_bytes(audit_bytes)
        manifest = {
            "schema_version": "1",
            "scope": "local authored controls; not model scoring",
            "inventory": descriptor("inventory.json", inventory_bytes),
            "reviews": [descriptor(name, data) for name, data in reviews.items()],
            "audit": descriptor("audit.json", audit_bytes),
        }
        (staging / "manifest.json").write_bytes(canonical(manifest))
        verified = verify_admission_bundle(staging, cache)
        require(verified["verified"], "Staged admission bundle failed verification")
        staging.rename(output)
    return verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.cache, arguments.output), indent=2))

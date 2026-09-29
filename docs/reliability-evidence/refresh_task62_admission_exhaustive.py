"""Advance the admission snapshot to protected task-62 exhaustive v2 evidence."""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from graybench.admission_bundle import verify_admission_bundle
from graybench.datasets import load_suite
from graybench.identity import canonical, identity
from graybench.oracle_review import inspect_oracle_review
from graybench.protected_oracle_review import protected_probes
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task62 import REQUIREMENT, task62_value_task_v2
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest
from graybench.task_admission import (
    AdmissionInventory,
    RequirementEvidence,
    admission_blockers,
    audit_control_coverage,
    refresh_finding_registry,
    require_current_finding_registry,
    validate_inventory,
)

HERE = Path(__file__).resolve().parent
PREDECESSOR = HERE / "artifacts/admission-task62-current-2026-09-28"
CURRENT = HERE / "artifacts/task62-protected-exhaustive-2026-09-28"
OLD_REVIEW_NAME = "task62-current-source.jsonl"
NEW_REVIEW_NAME = "task62-exhaustive-v2.jsonl"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
POSITIVE = ("analytic-bb84", "qiskit-bb84", "global-phase-bb84")
NEGATIVE = (
    "fixed-zero-bb84",
    "ignored-state-bb84",
    "ignored-basis-bb84",
    "reversed-order-bb84",
    "wrong-x-sign-bb84",
    "omitted-input-bb84",
)


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


def build(cache: Path, output: Path) -> dict:
    require(not output.exists(), "Output bundle already exists")
    require(verify_admission_bundle(PREDECESSOR, cache)["verified"], "Predecessor failed")
    prior_manifest = json.loads((PREDECESSOR / "manifest.json").read_bytes())
    prior_inventory = AdmissionInventory.model_validate_json(
        read_pinned(PREDECESSOR / prior_manifest["inventory"]["file"], prior_manifest["inventory"])
    )
    validate_inventory(prior_inventory, cache)
    try:
        require_current_finding_registry(prior_inventory)
    except ValueError:
        pass
    else:
        raise ValueError("Predecessor unexpectedly has the current finding registry")
    inventory = refresh_finding_registry(prior_inventory, cache)
    source = source_manifest()
    require(inventory.source_digest == source["digest"], "Refreshed source identity differs")

    current_manifest = json.loads((CURRENT / "manifest.json").read_bytes())
    require(current_manifest["image"] == IMAGE, "Protected runtime image differs")
    require(current_manifest["source_digest"] == source["digest"], "Current control source differs")
    current_path = CURRENT / current_manifest["log"]["path"]
    current_data = read_pinned(current_path, current_manifest["log"])
    current_report = inspect_oracle_review(current_path, cache)
    require(
        current_report["locally_verified"]
        and current_report["source_digest"] == source["digest"]
        and current_report["control_count"] == current_report["controls_matching_expectation"] == 18
        and current_report["expected_passes"] == 6
        and current_report["expected_failures"] == 12
        and not current_report["unexpected_outcomes"]
        and not current_report["publication_eligible"],
        "Current task-62 controls differ",
    )
    header = json.loads(current_data.splitlines()[0])["event"]
    require(header["source"] == source, "Current control header source differs")
    events = [json.loads(line)["event"] for line in current_data.splitlines()]
    omitted_events = [
        event
        for event in events
        if event["kind"] == "result" and event["task_key"].endswith("/omitted-input-bb84")
    ]
    require(len(omitted_events) == 2, "Missing omitted-input controls")
    for event in omitted_events:
        cases = event["evidence"]["judgment"]["case_results"]
        require(len(cases) == 1364, "Omitted-input control did not run all cases")
        require(
            [case["case_id"] for case in cases if not case["passed"]]
            == ["width-4-state-1000-basis-0000"],
            "Omitted-input control failed at a different case",
        )
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=120.0))
    cards = list(inventory.cards)
    for suite in ("normal", "hard"):
        pinned = load_suite(suite, cache)[62]
        revision = task62_value_task_v2(pinned)
        key = f"{suite}/qiskitHumanEval/62"
        declared = judge.manifest(revision)
        require(
            identity(header["selection"]["declared_judges"][key]) == identity(declared),
            "Task-62 v2 declared judge differs",
        )
        probes = {probe.name: probe for probe in protected_probes(pinned, oracle=revision.oracle)}
        require(set(probes) == set(POSITIVE + NEGATIVE), "Task-62 v2 probes differ")
        case_digests = {}
        for name, probe in probes.items():
            case_key = f"{key}/{name}"
            metadata = {
                "task_digest": pinned.digest,
                "expectation": probe.expectation,
                "rationale": probe.rationale,
                "completion": probe.completion,
            }
            require(header["selection"]["cases"][case_key] == metadata, "Probe differs")
            require(header["tasks"][case_key] == identity(metadata), "Probe identity differs")
            case_digests[name] = identity(metadata)
        index = next(i for i, card in enumerate(cards) if card.source_key == key)
        card = cards[index]
        require(
            card.public_contract_digest == revision.contract.digest
            and card.protected_judge_digest is not None
            and card.protected_judge_digest != identity(declared)
            and len(card.requirements) == 1
            and card.requirements[0].requirement_id == "bb84-sender-amplitudes"
            and card.requirements[0].public_clause == REQUIREMENT
            and not card.requirements[0].oracle_case_digests
            and not card.finding_resolutions
            and not card.reviews,
            "Prior task-62 card differs from expected pending v1 binding",
        )
        requirement = RequirementEvidence(
            requirement_id="bb84-sender-amplitudes",
            public_clause=REQUIREMENT,
            independent_alternative_digests=tuple(case_digests[name] for name in POSITIVE),
            wrong_mutant_digests=tuple(case_digests[name] for name in NEGATIVE),
        )
        cards[index] = card.model_copy(
            update={"protected_judge_digest": identity(declared), "requirements": (requirement,)}
        )
        require("known_findings_unresolved" in admission_blockers(cards[index]), "Finding vanished")

    inventory = inventory.model_copy(update={"cards": tuple(cards)})
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    require(not inventory.publication_eligible, "Inventory cannot publish")
    inventory_bytes = canonical(inventory.model_dump(mode="json"))

    reviews = {}
    replaced = False
    for record in prior_manifest["reviews"]:
        name = record["file"]
        data = read_pinned(PREDECESSOR / name, record)
        if name == OLD_REVIEW_NAME:
            require(not replaced, "Duplicate previous task-62 control log")
            reviews[NEW_REVIEW_NAME] = current_data
            replaced = True
        else:
            reviews[name] = data
    require(replaced and len(reviews) == len(prior_manifest["reviews"]) == 4, "Review set differs")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gb-task62-v2-admission-", dir=output.parent) as tmp:
        staging = Path(tmp) / "bundle"
        staging.mkdir()
        (staging / "inventory.json").write_bytes(inventory_bytes)
        for name, data in reviews.items():
            (staging / name).write_bytes(data)
        audit = audit_control_coverage(inventory, cache, tuple(staging / name for name in reviews))
        audit_counts = {
            name: audit[name]
            for name in (
                "control_count",
                "covered_task_count",
                "uncovered_task_count",
                "declared_frozen_judge_control_count",
                "false_pass_count",
                "false_rejection_count",
            )
        }
        require(
            audit["control_count"] == 60
            and audit["covered_task_count"] == 10
            and audit["uncovered_task_count"] == 292
            and audit["declared_frozen_judge_control_count"] == 42
            and audit["false_pass_count"] == 8
            and audit["false_rejection_count"] == 0
            and not audit["publication_eligible"],
            f"Exhaustive-v2 admission audit differs: {audit_counts}",
        )
        for suite in ("normal", "hard"):
            row = next(
                row for row in audit["tasks"] if row["task_key"] == f"{suite}/qiskitHumanEval/62"
            )
            require(len(row["controls"]) == 9, "Task-62 v2 control coverage differs")
            require(
                len(row["evidence_links"]) == 9
                and all(
                    link["status"] == "matching_local_observation" for link in row["evidence_links"]
                ),
                "Task-62 v2 requirement links differ",
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
        require(verified["verified"], "Staged successor failed verification")
        staging.rename(output)
    return verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.cache, arguments.output), indent=2))

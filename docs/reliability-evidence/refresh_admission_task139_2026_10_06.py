"""Bind task-139 protected controls in a development-only admission successor."""

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
from graybench.protected_task139 import REQUIREMENT
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest
from graybench.task_admission import (
    AdmissionInventory,
    RequirementEvidence,
    audit_control_coverage,
    require_current_finding_registry,
    validate_inventory,
)

HERE = Path(__file__).resolve().parent
PREDECESSOR = HERE / "artifacts/admission-current-controls-2026-10-06-v2"
CONTROLS = HERE / "artifacts/task139-protected-controls-2026-10-06-v2/results.jsonl"
CONTROL_SHA256 = "2324511dc885a4f2ee0d76228ae5da0d732fe6c548b1d1ae06b643d35ca5bc5f"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
NEW_REVIEW = "protected-task139-current.jsonl"


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
    prior = verify_admission_bundle(PREDECESSOR, cache)
    require(
        prior["verified"]
        and prior["control_count"] == 60
        and prior["inventory_source_bound_control_count"] == 42
        and prior["false_pass_count"] == 8
        and not prior["publication_eligible"],
        "Predecessor admission differs",
    )
    manifest = json.loads((PREDECESSOR / "manifest.json").read_bytes())
    inventory = AdmissionInventory.model_validate_json(
        read_pinned(PREDECESSOR / "inventory.json", manifest["inventory"])
    )
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    source = source_manifest()
    require(inventory.source_digest == source["digest"], "Predecessor source differs")

    control_bytes = CONTROLS.read_bytes()
    require(
        hashlib.sha256(control_bytes).hexdigest() == CONTROL_SHA256,
        "Task-139 control bytes differ",
    )
    report = inspect_oracle_review(CONTROLS, cache)
    require(
        report["locally_verified"]
        and report["file_sha256"] == CONTROL_SHA256
        and report["source_digest"] == source["digest"]
        and report["control_count"] == 22
        and report["controls_matching_expectation"] == 22
        and report["expected_passes"] == 10
        and report["expected_failures"] == 10
        and report["expected_candidate_errors"] == 2
        and not report["unexpected_outcomes"]
        and not report["independent_review"]
        and not report["publication_eligible"],
        "Task-139 control report differs",
    )
    header = json.loads(control_bytes.splitlines()[0])["event"]
    require(header["source"] == source, "Task-139 control header source differs")
    expected_keys = {f"{suite}/qiskitHumanEval/139" for suite in ("normal", "hard")}
    require(
        set(header["selection"]["declared_judges"]) == expected_keys,
        "Task-139 judge population differs",
    )

    cards = list(inventory.cards)
    expected_cases = set()
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=120.0))
    for key in sorted(expected_keys):
        suite = key.split("/", 1)[0]
        pinned = load_suite(suite, cache)[139]
        revision = revised_value_task(pinned)
        declared = judge.manifest(revision)
        require(
            header["selection"]["declared_judges"][key] == declared,
            f"Predeclared judge differs: {key}",
        )
        index = next(i for i, card in enumerate(cards) if card.source_key == key)
        card = cards[index]
        require(
            card.source_task_digest == pinned.digest
            and card.public_contract_digest is None
            and card.protected_judge_digest is None
            and not card.requirements
            and not card.finding_resolutions
            and not card.reviews
            and card.known_findings,
            f"Predecessor task-139 card differs: {key}",
        )
        positive, negative, rejected = set(), set(), set()
        for probe in protected_probes(pinned, oracle=revision.oracle):
            case_key = f"{key}/{probe.name}"
            metadata = {
                "task_digest": pinned.digest,
                "expectation": probe.expectation,
                "rationale": probe.rationale,
                "completion": probe.completion,
            }
            require(
                header["selection"]["cases"][case_key] == metadata
                and header["tasks"][case_key] == identity(metadata),
                f"Predeclared control differs: {case_key}",
            )
            expected_cases.add(case_key)
            digest = identity(metadata)
            if probe.expectation == "pass":
                positive.add(digest)
            elif probe.expectation == "fail":
                negative.add(digest)
            elif probe.expectation == "candidate_error":
                rejected.add(digest)
            else:
                raise ValueError(f"Unknown task-139 control expectation: {probe.expectation}")
        require(
            len(positive) == len(negative) == 5 and len(rejected) == 1,
            f"Task-139 control classes differ: {key}",
        )
        requirement = RequirementEvidence(
            requirement_id="schmidt-value",
            public_clause=REQUIREMENT,
            independent_alternative_digests=tuple(sorted(positive)),
            wrong_mutant_digests=tuple(sorted(negative)),
        )
        cards[index] = card.model_copy(
            update={
                "public_contract_digest": revision.contract.digest,
                "protected_judge_digest": identity(declared),
                "requirements": (requirement,),
            }
        )
    require(
        set(header["selection"]["cases"]) == expected_cases
        and set(header["tasks"]) == expected_cases,
        "Task-139 case population differs",
    )
    inventory = inventory.model_copy(update={"cards": tuple(cards)})
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    require(not inventory.publication_eligible, "Inventory cannot publish")
    inventory_bytes = canonical(inventory.model_dump(mode="json"))

    reviews = {
        record["file"]: read_pinned(PREDECESSOR / record["file"], record)
        for record in manifest["reviews"]
    }
    require(len(reviews) == 3 and NEW_REVIEW not in reviews, "Predecessor reviews differ")
    reviews[NEW_REVIEW] = control_bytes
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gb-task139-admission-", dir=output.parent) as tmp:
        staging = Path(tmp) / "bundle"
        staging.mkdir()
        (staging / "inventory.json").write_bytes(inventory_bytes)
        for name, data in reviews.items():
            (staging / name).write_bytes(data)
        audit = audit_control_coverage(inventory, cache, tuple(staging / name for name in reviews))
        require(
            audit["control_count"] == 82
            and audit["covered_task_count"] == 12
            and audit["uncovered_task_count"] == 290
            and audit["declared_frozen_judge_control_count"] == 64
            and audit["false_pass_count"] == 8
            and audit["false_rejection_count"] == 0
            and not audit["publication_eligible"],
            "Task-139 admission audit differs",
        )
        for row in audit["tasks"]:
            if row["task_key"] not in expected_keys:
                continue
            require(
                len(row["controls"]) == 11
                and all(
                    control["declared_frozen_judge_matches_card"] for control in row["controls"]
                )
                and len(row["evidence_links"]) == 10
                and all(
                    link["status"] == "matching_local_observation" for link in row["evidence_links"]
                )
                and sum(control["expected"] == "candidate_error" for control in row["controls"])
                == 1,
                f"Task-139 requirement links differ: {row['task_key']}",
            )
        audit_bytes = canonical(audit)
        (staging / "audit.json").write_bytes(audit_bytes)
        successor_manifest = {
            "schema_version": "1",
            "scope": "local authored controls; not model scoring",
            "inventory": descriptor("inventory.json", inventory_bytes),
            "reviews": [descriptor(name, data) for name, data in reviews.items()],
            "audit": descriptor("audit.json", audit_bytes),
        }
        (staging / "manifest.json").write_bytes(canonical(successor_manifest))
        verified = verify_admission_bundle(staging, cache)
        require(
            verified["verified"]
            and verified["inventory_source_bound_control_count"] == 64
            and verified["different_source_bound_control_count"] == 0
            and verified["inventory_source_matches_running_source"],
            "Task-139 successor source identity differs",
        )
        staging.rename(output)
    return verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.cache, args.output), indent=2))

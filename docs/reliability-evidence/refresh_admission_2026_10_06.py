"""Rebind six protected value cards to verified current-source controls.

This creates a development-only successor of the historical admission bundle.
It preserves earlier native observations and adds no reviewer attestations.
"""

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
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest
from graybench.task_admission import (
    AdmissionInventory,
    audit_control_coverage,
    refresh_finding_registry,
    require_current_finding_registry,
    validate_inventory,
)

HERE = Path(__file__).resolve().parent
PREDECESSOR = HERE / "artifacts/admission-current-controls-2026-09-28"
CONTROLS = HERE / "artifacts/protected-current-controls-2026-10-06-v2/results.jsonl"
CONTROL_SHA256 = "c0340de484f8430d94a74476f328ccff7ebf005b3ff4b5c9ab2ef936e2e622b7"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
OLD_PROTECTED = {"protected-task2-20-current.jsonl", "protected-task62-current.jsonl"}
NEW_PROTECTED = "protected-current-source.jsonl"


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
        read_pinned(PREDECESSOR / "inventory.json", prior_manifest["inventory"])
    )
    validate_inventory(prior_inventory, cache)
    require_current_finding_registry(prior_inventory)

    source = source_manifest()
    control_bytes = CONTROLS.read_bytes()
    require(
        hashlib.sha256(control_bytes).hexdigest() == CONTROL_SHA256,
        "Current protected control bytes differ",
    )
    control_report = inspect_oracle_review(CONTROLS, cache)
    require(
        control_report["locally_verified"]
        and control_report["source_digest"] == source["digest"]
        and control_report["file_sha256"] == CONTROL_SHA256
        and control_report["control_count"] == 42
        and control_report["controls_matching_expectation"] == 42
        and control_report["expected_passes"] == 18
        and control_report["expected_failures"] == 24
        and not control_report["unexpected_outcomes"]
        and not control_report["independent_review"]
        and not control_report["publication_eligible"],
        "Current protected controls differ",
    )
    header = json.loads(control_bytes.splitlines()[0])["event"]
    require(header["source"] == source, "Protected control header source differs")
    expected_keys = {
        f"{suite}/qiskitHumanEval/{number}"
        for suite in ("normal", "hard")
        for number in (2, 20, 62)
    }
    require(
        set(header["selection"]["declared_judges"]) == expected_keys,
        "Protected judge population differs",
    )

    inventory = refresh_finding_registry(prior_inventory, cache)
    require(inventory.source_digest == source["digest"], "Refreshed source differs")
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=120.0))
    cards = list(inventory.cards)
    expected_cases = set()
    for key in sorted(expected_keys):
        suite, _, number = key.partition("/qiskitHumanEval/")
        pinned = load_suite(suite, cache)[int(number)]
        revision = revised_value_task(pinned)
        declared = judge.manifest(revision)
        require(
            identity(header["selection"]["declared_judges"][key]) == identity(declared),
            f"Predeclared judge differs: {key}",
        )
        index = next(i for i, card in enumerate(cards) if card.source_key == key)
        card = cards[index]
        require(
            card.public_contract_digest == revision.contract.digest
            and card.protected_judge_digest is not None
            and card.requirements
            and not card.finding_resolutions
            and not card.reviews,
            f"Predecessor card differs: {key}",
        )
        positive = set()
        negative = set()
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
            (positive if probe.expectation == "pass" else negative).add(identity(metadata))
        require(
            {
                digest
                for item in card.requirements
                for digest in item.independent_alternative_digests
            }
            == positive
            and {digest for item in card.requirements for digest in item.wrong_mutant_digests}
            == negative
            and all(not item.oracle_case_digests for item in card.requirements),
            f"Requirement control identities differ: {key}",
        )
        cards[index] = card.model_copy(update={"protected_judge_digest": identity(declared)})
    require(
        set(header["selection"]["cases"]) == expected_cases
        and set(header["tasks"]) == expected_cases,
        "Protected case population differs",
    )
    inventory = inventory.model_copy(update={"cards": tuple(cards)})
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    require(not inventory.publication_eligible, "Inventory cannot publish")
    inventory_bytes = canonical(inventory.model_dump(mode="json"))

    reviews = {}
    replaced = set()
    for record in prior_manifest["reviews"]:
        old_name = record["file"]
        old_data = read_pinned(PREDECESSOR / old_name, record)
        if old_name in OLD_PROTECTED:
            replaced.add(old_name)
        else:
            reviews[old_name] = old_data
    require(replaced == OLD_PROTECTED and len(reviews) == 2, "Review replacement differs")
    reviews[NEW_PROTECTED] = control_bytes

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gb-current-admission-", dir=output.parent) as tmp:
        staging = Path(tmp) / "bundle"
        staging.mkdir()
        (staging / "inventory.json").write_bytes(inventory_bytes)
        for name, data in reviews.items():
            (staging / name).write_bytes(data)
        audit = audit_control_coverage(inventory, cache, tuple(staging / name for name in reviews))
        require(
            audit["control_count"] == 60
            and audit["covered_task_count"] == 10
            and audit["uncovered_task_count"] == 292
            and audit["declared_frozen_judge_control_count"] == 42
            and audit["false_pass_count"] == 8
            and audit["false_rejection_count"] == 0
            and not audit["publication_eligible"],
            "Successor admission audit differs",
        )
        for row in audit["tasks"]:
            if row["task_key"] in expected_keys:
                require(
                    bool(row["evidence_links"])
                    and all(
                        link["status"] == "matching_local_observation"
                        for link in row["evidence_links"]
                    ),
                    f"Current-source requirement links differ: {row['task_key']}",
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
        require(
            verified["verified"]
            and verified["inventory_source_bound_control_count"] == 42
            and verified["different_source_bound_control_count"] == 0
            and verified["inventory_source_matches_running_source"],
            "Successor source identity differs",
        )
        staging.rename(output)
    return verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.cache, arguments.output), indent=2))

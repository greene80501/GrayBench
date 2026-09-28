"""Build a source-bound, publication-ineligible task-62 admission successor."""

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
from graybench.protected_task62 import REQUIREMENT, task62_value_task
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
PREDECESSOR = HERE / "artifacts/admission-findings-2026-09-28"
TASK62 = HERE / "artifacts/task62-protected-value-2026-09-28"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def descriptor(name: str, data: bytes) -> dict:
    return {"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def build(cache: Path, output: Path) -> dict:
    require(not output.exists(), "Output bundle already exists")
    require(verify_admission_bundle(PREDECESSOR, cache)["verified"], "Predecessor failed")
    predecessor_manifest = json.loads((PREDECESSOR / "manifest.json").read_bytes())
    previous_inventory = AdmissionInventory.model_validate_json(
        (PREDECESSOR / predecessor_manifest["inventory"]["file"]).read_bytes()
    )
    require_current_finding_registry(previous_inventory)

    task62_manifest = json.loads((TASK62 / "manifest.json").read_bytes())
    task62_log = TASK62 / task62_manifest["log"]["path"]
    task62_bytes = task62_log.read_bytes()
    require(
        len(task62_bytes) == task62_manifest["log"]["bytes"]
        and hashlib.sha256(task62_bytes).hexdigest() == task62_manifest["log"]["sha256"],
        "Task-62 control bytes differ",
    )
    report = inspect_oracle_review(task62_log, cache)
    require(
        report["locally_verified"]
        and not report["publication_eligible"]
        and report["control_count"] == report["controls_matching_expectation"] == 16
        and not report["unexpected_outcomes"]
        and report["source_digest"] == source_manifest()["digest"],
        "Task-62 control report differs from current source",
    )
    header = json.loads(task62_bytes.splitlines()[0])["event"]
    require(header["source"] == source_manifest(), "Task-62 source manifest differs")
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE))
    cards = list(previous_inventory.cards)
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[62]
        revision = task62_value_task(source)
        key = f"{suite}/qiskitHumanEval/62"
        declared = judge.manifest(revision)
        require(
            header["selection"]["declared_judges"][key] == declared,
            "Task-62 declared judge differs",
        )
        require(declared["runner"]["image"] == IMAGE, "Task-62 image differs")
        probes = {probe.name: probe for probe in protected_probes(source)}
        require(len(probes) == 8, "Task-62 authored probe count differs")
        case_digests = {}
        for name, probe in probes.items():
            case_key = f"{key}/{name}"
            metadata = {
                "task_digest": source.digest,
                "expectation": probe.expectation,
                "rationale": probe.rationale,
                "completion": probe.completion,
            }
            require(
                header["selection"]["cases"][case_key] == metadata, "Task-62 authored probe differs"
            )
            require(
                header["tasks"][case_key] == identity(metadata), "Task-62 probe identity differs"
            )
            case_digests[name] = identity(metadata)
        card_index = next(i for i, card in enumerate(cards) if card.source_key == key)
        card = cards[card_index]
        require(
            card.public_contract_digest is None
            and card.protected_judge_digest is None
            and not card.requirements
            and not card.finding_resolutions
            and not card.reviews,
            "Task-62 card already carries review claims",
        )
        requirement = RequirementEvidence(
            requirement_id="bb84-sender-amplitudes",
            public_clause=REQUIREMENT,
            independent_alternative_digests=tuple(
                case_digests[name] for name in ("analytic-bb84", "qiskit-bb84", "global-phase-bb84")
            ),
            wrong_mutant_digests=tuple(
                case_digests[name]
                for name in (
                    "fixed-zero-bb84",
                    "ignored-state-bb84",
                    "ignored-basis-bb84",
                    "reversed-order-bb84",
                    "wrong-x-sign-bb84",
                )
            ),
        )
        cards[card_index] = card.model_copy(
            update={
                "public_contract_digest": revision.contract.digest,
                "protected_judge_digest": identity(declared),
                "requirements": (requirement,),
            }
        )

    inventory = previous_inventory.model_copy(
        update={"source_digest": source_manifest()["digest"], "cards": tuple(cards)}
    )
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    review_data = {
        entry["file"]: (PREDECESSOR / entry["file"]).read_bytes()
        for entry in predecessor_manifest["reviews"]
    }
    review_data["GrayBench-v3-task62-protected-controls-both-20260928.jsonl"] = task62_bytes
    # Keep final paths short enough for Windows Python without long-path policy.
    inventory_name = "inventory.json"
    audit_name = "audit.json"
    inventory_bytes = canonical(inventory.model_dump(mode="json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="graybench-task62-admission-", dir=output.parent
    ) as tmp:
        staging = Path(tmp) / "bundle"
        staging.mkdir()
        (staging / inventory_name).write_bytes(inventory_bytes)
        for name, data in review_data.items():
            (staging / name).write_bytes(data)
        audit = audit_control_coverage(
            inventory, cache, tuple(staging / name for name in review_data)
        )
        require(
            audit["control_count"] == 58
            and audit["covered_task_count"] == 10
            and audit["uncovered_task_count"] == 292
            and audit["declared_frozen_judge_control_count"] == 40
            and audit["false_pass_count"] == 8
            and not audit["publication_eligible"],
            "Task-62 successor audit differs from expected coverage",
        )
        audit_bytes = canonical(audit)
        (staging / audit_name).write_bytes(audit_bytes)
        manifest = {
            "schema_version": "1",
            "scope": "local authored controls; not model scoring",
            "inventory": descriptor(inventory_name, inventory_bytes),
            "reviews": [descriptor(name, data) for name, data in review_data.items()],
            "audit": descriptor(audit_name, audit_bytes),
        }
        (staging / "manifest.json").write_bytes(canonical(manifest))
        verified = verify_admission_bundle(staging, cache)
        staging.rename(output)
    return verified


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.cache, arguments.output), indent=2))

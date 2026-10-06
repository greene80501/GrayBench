"""Build an exact private-call roster for the six current protected value revisions.

This is a review packet, not a requirement-to-case coverage decision or an
independent attestation. It deliberately leaves requirement-case links empty.
"""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.admission_bundle import verify_admission_bundle
from graybench.datasets import load_suite
from graybench.identity import canonical, identity
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest
from graybench.task_admission import (
    AdmissionInventory,
    require_current_finding_registry,
    validate_inventory,
)

HERE = Path(__file__).resolve().parent
BUNDLE = HERE / "artifacts/admission-current-controls-2026-10-06-v2"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
TASK_NUMBERS = (2, 20, 62)


def build(cache: Path) -> dict:
    """Recreate each call from pinned inputs and the source-bound admission cards."""
    verified = verify_admission_bundle(BUNDLE, cache)
    if not verified["verified"] or not verified["inventory_source_matches_running_source"]:
        raise ValueError("Admission bundle does not match current pinned source")
    inventory_bytes = (BUNDLE / "inventory.json").read_bytes()
    inventory = AdmissionInventory.model_validate_json(inventory_bytes)
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    source_digest = source_manifest()["digest"]
    if inventory.source_digest != source_digest:
        raise ValueError("Admission inventory does not match current pinned source")

    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=120.0))
    cards = {card.source_key: card for card in inventory.cards}
    tasks = []
    for suite in ("normal", "hard"):
        pinned = load_suite(suite, cache)
        for number in TASK_NUMBERS:
            source = pinned[number]
            key = f"{suite}/qiskitHumanEval/{number}"
            card = cards[key]
            revision = revised_value_task(source)
            manifest = judge.manifest(revision)
            if (
                card.source_task_digest != source.digest
                or card.public_contract_digest != revision.contract.digest
                or card.protected_judge_digest != identity(manifest)
                or not card.requirements
                or card.reviews
            ):
                raise ValueError(f"Admission card does not match current pinned source: {key}")
            cases = [
                {
                    "case_id": case.case_id,
                    "call": case.call.model_dump(mode="json"),
                    "digest": identity(case.model_dump(mode="json")),
                }
                for case in revision.cases
            ]
            if (
                identity([case.model_dump(mode="json") for case in revision.cases])
                != manifest["private_case_digest"]
            ):
                raise ValueError(f"Private call roster differs from judge: {key}")
            tasks.append(
                {
                    "source_key": key,
                    "source_task_digest": source.digest,
                    "public_contract_digest": revision.contract.digest,
                    "protected_judge_digest": card.protected_judge_digest,
                    "judge_manifest": manifest,
                    "requirements": [
                        {
                            "requirement_id": item.requirement_id,
                            "public_clause": item.public_clause,
                        }
                        for item in card.requirements
                    ],
                    "requirement_case_links": [],
                    "cases": cases,
                }
            )
    return {
        "schema_version": "1",
        "scope": "private call inventory for independent review; semantic adequacy unverified",
        "source_digest": source_digest,
        "admission_inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "publication_eligible": False,
        "independent_review": False,
        "tasks": tasks,
    }


def verify(packet: dict, cache: Path) -> bool:
    """Reject altered calls, clauses, source, or judge bindings by exact recreation."""
    if canonical(packet) != canonical(build(cache)):
        raise ValueError("Oracle case roster differs from current pinned source")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        verify(json.loads(args.output.read_bytes()), args.cache)
    else:
        args.output.write_bytes(canonical(build(args.cache)))


if __name__ == "__main__":
    main()

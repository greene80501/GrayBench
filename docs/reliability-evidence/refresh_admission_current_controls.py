"""Build a verified admission successor from one source-bound protected control set."""

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
PREDECESSOR = HERE / "artifacts/admission-task62-exhaustive-2026-09-28"
CONTROLS = HERE / "artifacts/protected-controls-current-source-2026-09-28"
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
REPLACEMENTS = {
    "GrayBench-v3-protected-controls-both-final-20260928.jsonl": (
        "task2-20.jsonl",
        "protected-task2-20-current.jsonl",
    ),
    "task62-exhaustive-v2.jsonl": (
        "task62-exhaustive-v2.jsonl",
        "protected-task62-current.jsonl",
    ),
}


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


def _current_logs(cache: Path, source: dict) -> tuple[dict, dict]:
    manifest = json.loads((CONTROLS / "manifest.json").read_bytes())
    require(
        isinstance(manifest, dict)
        and set(manifest) == {"schema_version", "image", "source_digest", "scope", "logs"}
        and manifest["schema_version"] == "1"
        and manifest["image"] == IMAGE
        and manifest["source_digest"] == source["digest"]
        and manifest["scope"] == "local authored protected value controls; no model score"
        and isinstance(manifest["logs"], list)
        and len(manifest["logs"]) == 2
        and all(
            isinstance(record, dict) and set(record) == {"file", "bytes", "sha256"}
            for record in manifest["logs"]
        )
        and [record["file"] for record in manifest["logs"]]
        == ["task2-20.jsonl", "task62-exhaustive-v2.jsonl"],
        "Current control manifest differs",
    )
    data = {}
    headers = {}
    for record, count, passes, failures in zip(
        manifest["logs"], (24, 18), (12, 6), (12, 12), strict=True
    ):
        name = record["file"]
        path = CONTROLS / name
        data[name] = read_pinned(path, record)
        report = inspect_oracle_review(path, cache)
        require(
            report["locally_verified"]
            and report["source_digest"] == source["digest"]
            and report["control_count"] == report["controls_matching_expectation"] == count
            and report["expected_passes"] == passes
            and report["expected_failures"] == failures
            and not report["unexpected_outcomes"]
            and not report["publication_eligible"],
            f"Current protected controls differ: {name}",
        )
        headers[name] = json.loads(data[name].splitlines()[0])["event"]
        require(headers[name]["source"] == source, f"Control header source differs: {name}")
    task62_events = [
        json.loads(line)["event"] for line in data["task62-exhaustive-v2.jsonl"].splitlines()
    ]
    omitted = [
        event
        for event in task62_events
        if event["kind"] == "result" and event["task_key"].endswith("/omitted-input-bb84")
    ]
    require(len(omitted) == 2, "Missing task-62 omitted-input controls")
    for event in omitted:
        cases = event["evidence"]["judgment"]["case_results"]
        require(
            len(cases) == 1364
            and [case["case_id"] for case in cases if not case["passed"]]
            == ["width-4-state-1000-basis-0000"],
            "Task-62 omitted-input control differs",
        )
    return data, headers


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
    logs, headers = _current_logs(cache, source)
    inventory = refresh_finding_registry(prior_inventory, cache)
    require(inventory.source_digest == source["digest"], "Refreshed source differs")

    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=120.0))
    expected_keys = {
        "task2-20.jsonl": {
            f"{suite}/qiskitHumanEval/{number}"
            for suite in ("normal", "hard")
            for number in (2, 20)
        },
        "task62-exhaustive-v2.jsonl": {
            f"{suite}/qiskitHumanEval/62" for suite in ("normal", "hard")
        },
    }
    cards = list(inventory.cards)
    rebound = set()
    for name, keys in expected_keys.items():
        header = headers[name]
        require(
            set(header["selection"]["declared_judges"]) == keys,
            f"Predeclared judge keys differ: {name}",
        )
        expected_cases = set()
        for key in sorted(keys):
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
            rebound.add(key)
        require(
            set(header["selection"]["cases"]) == expected_cases
            and set(header["tasks"]) == expected_cases,
            f"Predeclared case population differs: {name}",
        )
    require(len(rebound) == 6, "Expected six protected cards")
    inventory = inventory.model_copy(update={"cards": tuple(cards)})
    validate_inventory(inventory, cache)
    require_current_finding_registry(inventory)
    require(not inventory.publication_eligible, "Inventory cannot publish")
    inventory_bytes = canonical(inventory.model_dump(mode="json"))

    reviews = {}
    replacements = set()
    for record in prior_manifest["reviews"]:
        old_name = record["file"]
        old_data = read_pinned(PREDECESSOR / old_name, record)
        if old_name in REPLACEMENTS:
            source_name, new_name = REPLACEMENTS[old_name]
            reviews[new_name] = logs[source_name]
            replacements.add(old_name)
        else:
            reviews[old_name] = old_data
    require(replacements == set(REPLACEMENTS) and len(reviews) == 4, "Review replacement differs")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gb-current-controls-", dir=output.parent) as tmp:
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
            if row["task_key"] in rebound:
                require(
                    all(
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

"""Pinned QHE ancestry and evidence checklists for protected task admission.

This records what remains to be reviewed. Structural evidence references do not
authenticate reviewer identity or prove that an oracle is semantically adequate.
"""

import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from graybench.contracts import Contract
from graybench.datasets import EXTERNAL_IDS, KNOWN_FINDINGS, PINS, load_suite
from graybench.oracle_review import inspect_oracle_review
from graybench.provenance import source_manifest

HEX = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_KEY = re.compile(r"(normal|hard)/qiskitHumanEval/(\d+)\Z")
TRACK = "graybench-protected-semantic-v1"


def _digest(value: str) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _finding_digest(finding: str) -> str:
    return hashlib.sha256(finding.encode("utf-8")).hexdigest()


class RequirementEvidence(Contract):
    requirement_id: str = Field(min_length=1)
    public_clause: str = Field(min_length=1)
    oracle_case_digests: tuple[str, ...] = ()
    independent_alternative_digests: tuple[str, ...] = ()
    wrong_mutant_digests: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_evidence(self) -> "RequirementEvidence":
        if not self.requirement_id.strip() or not self.public_clause.strip():
            raise ValueError("Requirement identity and clause must be nonempty")
        for group in (
            self.oracle_case_digests,
            self.independent_alternative_digests,
            self.wrong_mutant_digests,
        ):
            if len(set(group)) != len(group) or any(not _digest(value) for value in group):
                raise ValueError("Requirement evidence identities must be unique SHA-256 digests")
        groups = (
            set(self.oracle_case_digests),
            set(self.independent_alternative_digests),
            set(self.wrong_mutant_digests),
        )
        if any(groups[left] & groups[right] for left, right in ((0, 1), (0, 2), (1, 2))):
            raise ValueError("Control evidence identities must be disjoint across outcomes")
        return self


class ReviewAttestation(Contract):
    reviewer_id: str = Field(min_length=1)
    qualification_digest: str | None = None
    review_artifact_digest: str | None = None
    decision: Literal["pending", "approve", "reject"] = "pending"

    @model_validator(mode="after")
    def valid_review(self) -> "ReviewAttestation":
        if not self.reviewer_id.strip() or any(
            value is not None and not _digest(value)
            for value in (self.qualification_digest, self.review_artifact_digest)
        ):
            raise ValueError("Invalid reviewer identity or evidence digest")
        return self


class TaskCard(Contract):
    track: Literal["graybench-protected-semantic-v1"] = TRACK
    source_suite: Literal["normal", "hard"]
    source_key: str
    source_task_digest: str
    public_contract_digest: str | None = None
    # Omit absent bindings when serializing old pending inventories, preserving
    # their existing identity while requiring an exact judge for new claims.
    protected_judge_digest: str | None = Field(default=None, exclude_if=lambda value: value is None)
    requirements: tuple[RequirementEvidence, ...] = ()
    known_findings: tuple[str, ...] = ()
    finding_resolutions: dict[str, str] = Field(default_factory=dict)
    external_service: bool
    dependency_status: Literal["offline", "external_service_unqualified", "qualified"]
    reviews: tuple[ReviewAttestation, ...] = ()

    @model_validator(mode="after")
    def valid_card(self) -> "TaskCard":
        match = SOURCE_KEY.fullmatch(self.source_key)
        if match is None or match[1] != self.source_suite or int(match[2]) > 150:
            raise ValueError("Task card must identify one pinned suite and task")
        if (
            not _digest(self.source_task_digest)
            or (
                self.public_contract_digest is not None and not _digest(self.public_contract_digest)
            )
            or (
                self.protected_judge_digest is not None and not _digest(self.protected_judge_digest)
            )
        ):
            raise ValueError("Invalid task, public-contract, or protected-judge identity")
        if self.external_service != (int(match[2]) in EXTERNAL_IDS):
            raise ValueError("External-service classification differs from pinned inventory")
        if self.external_service and self.dependency_status == "offline":
            raise ValueError("External-service task cannot claim offline qualification")
        if not self.external_service and self.dependency_status != "offline":
            raise ValueError("Offline task cannot claim external-service status")
        if len(set(self.known_findings)) != len(self.known_findings) or any(
            not item.strip() for item in self.known_findings
        ):
            raise ValueError("Invalid known-finding inventory")
        if set(self.finding_resolutions) - {
            _finding_digest(finding) for finding in self.known_findings
        } or any(not _digest(value) for value in self.finding_resolutions.values()):
            raise ValueError("Finding resolution must cite one known finding and evidence digest")
        if len({item.requirement_id for item in self.requirements}) != len(self.requirements):
            raise ValueError("Duplicate requirement identity")
        if len({item.reviewer_id for item in self.reviews}) != len(self.reviews):
            raise ValueError("Duplicate reviewer identity")
        return self


class AdmissionInventory(Contract):
    schema_version: Literal["1", "2"] = "1"
    track: Literal["graybench-protected-semantic-v1"] = TRACK
    source_pins: dict[str, dict[str, str]]
    source_digest: str
    cards: tuple[TaskCard, ...] = Field(min_length=302, max_length=302)

    @property
    def publication_eligible(self) -> bool:
        return False

    @model_validator(mode="after")
    def complete_pinned_population(self) -> "AdmissionInventory":
        expected = tuple(
            f"{suite}/qiskitHumanEval/{number}"
            for suite in ("normal", "hard")
            for number in range(151)
        )
        if tuple(card.source_key for card in self.cards) != expected:
            raise ValueError("Admission inventory must list all 302 pinned records in order")
        if set(self.source_pins) != {"normal", "hard"} or any(
            set(pin) != {"repo", "revision", "sha256"} or not all(pin.values())
            for pin in self.source_pins.values()
        ):
            raise ValueError("Admission inventory source pins are incomplete")
        if not _digest(self.source_digest):
            raise ValueError("Admission inventory source identity is invalid")
        return self


def admission_blockers(card: TaskCard) -> tuple[str, ...]:
    """Structural review checklist; empty does not establish release authenticity."""
    TaskCard.model_validate_json(card.model_dump_json())
    blockers = []
    if card.public_contract_digest is None:
        blockers.append("public_value_contract_missing")
    if card.protected_judge_digest is None:
        blockers.append("protected_judge_missing")
    if not card.requirements:
        blockers.append("requirements_missing")
    else:
        if any(not item.oracle_case_digests for item in card.requirements):
            blockers.append("oracle_cases_missing")
        if any(not item.independent_alternative_digests for item in card.requirements):
            blockers.append("independent_alternative_missing")
        if any(not item.wrong_mutant_digests for item in card.requirements):
            blockers.append("wrong_mutant_missing")
    if set(card.finding_resolutions) != {
        _finding_digest(finding) for finding in card.known_findings
    }:
        blockers.append("known_findings_unresolved")
    if card.external_service and card.dependency_status != "qualified":
        blockers.append("external_service_unqualified")
    qualified = [
        review
        for review in card.reviews
        if review.decision == "approve"
        and review.qualification_digest is not None
        and review.review_artifact_digest is not None
    ]
    if len({review.review_artifact_digest for review in qualified}) < 2:
        blockers.append("independent_review_missing")
    if any(review.decision == "reject" for review in card.reviews):
        blockers.append("review_rejection_unresolved")
    return tuple(blockers)


def validate_inventory(inventory: AdmissionInventory, cache: Path) -> None:
    """Re-read exact pinned bytes; caller-provided cards alone prove no provenance."""
    AdmissionInventory.model_validate_json(inventory.model_dump_json())
    if inventory.source_pins != PINS:
        raise ValueError("Admission inventory pinned dataset revision changed")
    # V1 conflated the source that created the checklist with the source that
    # later inspects it. V2 keeps that historical identity while allowing
    # task review to continue across unrelated engine edits.
    if inventory.schema_version == "1" and inventory.source_digest != source_manifest()["digest"]:
        raise ValueError("Admission inventory engine source changed")
    pinned = tuple(task for suite in ("normal", "hard") for task in load_suite(suite, cache))
    for card, task in zip(inventory.cards, pinned, strict=True):
        number = int(task.public.task_id.rsplit("/", 1)[1])
        if (
            card.source_suite != task.public.suite
            or card.source_key != f"{task.public.suite}/{task.public.task_id}"
            or card.source_task_digest != task.digest
            or card.known_findings != tuple(KNOWN_FINDINGS.get(number, ()))
            or card.external_service != (number in EXTERNAL_IDS)
        ):
            raise ValueError("Admission card differs from pinned task ancestry")


def build_pending_inventory(cache: Path) -> AdmissionInventory:
    tasks = tuple(task for suite in ("normal", "hard") for task in load_suite(suite, cache))
    cards = []
    for task in tasks:
        number = int(task.public.task_id.rsplit("/", 1)[1])
        external_service = number in EXTERNAL_IDS
        cards.append(
            TaskCard(
                source_suite=task.public.suite,
                source_key=f"{task.public.suite}/{task.public.task_id}",
                source_task_digest=task.digest,
                known_findings=tuple(KNOWN_FINDINGS.get(number, ())),
                external_service=external_service,
                dependency_status=(
                    "external_service_unqualified" if external_service else "offline"
                ),
            )
        )
    inventory = AdmissionInventory(
        schema_version="2",
        source_pins={suite: dict(pin) for suite, pin in PINS.items()},
        source_digest=source_manifest()["digest"],
        cards=tuple(cards),
    )
    validate_inventory(inventory, cache)
    return inventory


def _requirement_links(card: TaskCard, controls: list[dict]) -> list[dict]:
    """Check authored digest references against observed local candidate controls.

    Oracle-case digests identify test fixtures, which these candidate-control
    logs do not expose. Even a matching candidate case digest cannot verify one.
    """
    by_digest: dict[str, list[dict]] = {}
    for control in controls:
        by_digest.setdefault(control["case_digest"], []).append(control)
    links = []
    for requirement in card.requirements:
        for role, digests, expected in (
            ("oracle_case", requirement.oracle_case_digests, None),
            ("independent_alternative", requirement.independent_alternative_digests, "pass"),
            ("wrong_mutant", requirement.wrong_mutant_digests, "fail"),
        ):
            for digest in digests:
                observations = (
                    []
                    if role == "oracle_case"
                    else sorted(
                        by_digest.get(digest, []),
                        key=lambda item: (item["artifact_file_sha256"], item["case_key"]),
                    )
                )
                qualified = [
                    item for item in observations if item["declared_frozen_judge_matches_card"]
                ]
                if role == "oracle_case":
                    status = "unverified_fixture"
                elif not observations:
                    status = "missing_local_observation"
                elif not qualified:
                    status = "unqualified_judge_condition"
                elif any(
                    item["expected"] != expected or item["actual"] != expected for item in qualified
                ):
                    status = "unexpected_local_outcome"
                else:
                    status = "matching_local_observation"
                links.append(
                    {
                        "requirement_id": requirement.requirement_id,
                        "role": role,
                        "digest": digest,
                        "status": status,
                        "observations": observations,
                        "declared_frozen_judge_observation_count": len(qualified),
                    }
                )
    return links


def audit_control_coverage(
    inventory: AdmissionInventory, cache: Path, review_logs: tuple[Path, ...]
) -> dict:
    """Join verified local controls to every task card; never admit a task."""
    validate_inventory(inventory, cache)
    by_task = {card.source_key: [] for card in inventory.cards}
    cards = {card.source_key: card for card in inventory.cards}
    task_digests = {card.source_key: card.source_task_digest for card in inventory.cards}
    artifacts = []
    seen = set()
    for path in review_logs:
        report = inspect_oracle_review(path, cache)
        file_digest = report["file_sha256"]
        if file_digest in seen:
            raise ValueError("Duplicate oracle-review artifact")
        seen.add(file_digest)
        artifacts.append(
            {
                "file_sha256": file_digest,
                "chain_head": report["chain_head"],
                "source_digest": report["source_digest"],
                "control_count": report["control_count"],
            }
        )
        for control in report["controls"]:
            key = control["task_key"]
            if key not in by_task or control["task_digest"] != task_digests[key]:
                raise ValueError("Oracle control differs from inventory task ancestry")
            card = cards[key]
            by_task[key].append(
                {
                    **control,
                    "artifact_file_sha256": file_digest,
                    "declared_frozen_judge_matches_card": (
                        control["judge_manifest_verified"]
                        and control["judge_track"] == TRACK
                        and card.public_contract_digest is not None
                        and control["public_contract_digest"] == card.public_contract_digest
                        and card.protected_judge_digest is not None
                        and control["judge_digest"] == card.protected_judge_digest
                    ),
                }
            )
    rows = [
        {
            "task_key": card.source_key,
            "source_task_digest": card.source_task_digest,
            "controls": sorted(
                by_task[card.source_key],
                key=lambda control: (control["artifact_file_sha256"], control["case_key"]),
            ),
            "evidence_links": _requirement_links(card, by_task[card.source_key]),
        }
        for card in inventory.cards
    ]
    mismatches = [
        control
        for row in rows
        for control in row["controls"]
        if control["expected"] != control["actual"]
    ]
    false_passes = sum(
        control["expected"] == "fail" and control["actual"] == "pass" for control in mismatches
    )
    false_rejections = sum(
        control["expected"] == "pass" and control["actual"] == "fail" for control in mismatches
    )
    return {
        "schema_version": "4",
        "track": TRACK,
        "inventory_digest": inventory.digest,
        "source_pins": inventory.source_pins,
        "artifacts": sorted(artifacts, key=lambda item: item["file_sha256"]),
        "tasks": rows,
        "control_count": sum(len(row["controls"]) for row in rows),
        "covered_task_count": sum(bool(row["controls"]) for row in rows),
        "uncovered_task_count": sum(not row["controls"] for row in rows),
        "declared_frozen_judge_control_count": sum(
            control["declared_frozen_judge_matches_card"]
            for row in rows
            for control in row["controls"]
        ),
        "unexpected_outcome_count": len(mismatches),
        "false_pass_count": false_passes,
        "false_rejection_count": false_rejections,
        "other_mismatch_count": len(mismatches) - false_passes - false_rejections,
        "independent_review": False,
        "publication_eligible": False,
    }

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
        if not _digest(self.source_task_digest) or (
            self.public_contract_digest is not None and not _digest(self.public_contract_digest)
        ):
            raise ValueError("Invalid task or revised public-contract identity")
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
    schema_version: Literal["1"] = "1"
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
    return tuple(blockers)


def validate_inventory(inventory: AdmissionInventory, cache: Path) -> None:
    """Re-read exact pinned bytes; caller-provided cards alone prove no provenance."""
    AdmissionInventory.model_validate_json(inventory.model_dump_json())
    if inventory.source_pins != PINS:
        raise ValueError("Admission inventory pinned dataset revision changed")
    if inventory.source_digest != source_manifest()["digest"]:
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
        source_pins={suite: dict(pin) for suite, pin in PINS.items()},
        source_digest=source_manifest()["digest"],
        cards=tuple(cards),
    )
    validate_inventory(inventory, cache)
    return inventory

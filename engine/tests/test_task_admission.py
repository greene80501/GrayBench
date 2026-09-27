import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from test_native_cohort import cache as _synthetic_cache

from graybench.cli import main
from graybench.datasets import EXTERNAL_IDS, KNOWN_FINDINGS, PINS
from graybench.task_admission import (
    AdmissionInventory,
    RequirementEvidence,
    ReviewAttestation,
    TaskCard,
    admission_blockers,
    build_pending_inventory,
    validate_inventory,
)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    return _synthetic_cache.__wrapped__(tmp_path, monkeypatch)


def test_pending_inventory_contains_exact_pinned_302_and_no_admission(cache):
    inventory = build_pending_inventory(cache)
    assert inventory.track == "graybench-protected-semantic-v1"
    assert len(inventory.cards) == 302
    assert inventory.cards[0].source_key == "normal/qiskitHumanEval/0"
    assert inventory.cards[151].source_key == "hard/qiskitHumanEval/0"
    assert inventory.cards[-1].source_key == "hard/qiskitHumanEval/150"
    assert inventory.source_pins == PINS
    assert sum(card.external_service for card in inventory.cards) == 16
    assert all(card.public_contract_digest is None for card in inventory.cards)
    assert all(admission_blockers(card) for card in inventory.cards)
    assert inventory.publication_eligible is False
    for suite in ("normal", "hard"):
        for number in EXTERNAL_IDS:
            card = next(
                card
                for card in inventory.cards
                if card.source_key == f"{suite}/qiskitHumanEval/{number}"
            )
            assert card.dependency_status == "external_service_unqualified"
    assert inventory.cards[0].known_findings == tuple(KNOWN_FINDINGS[0])
    validate_inventory(inventory, cache)


def test_changed_source_file_or_card_is_rejected(cache):
    inventory = build_pending_inventory(cache)
    changed = inventory.model_copy(
        update={
            "cards": (
                inventory.cards[0].model_copy(update={"source_task_digest": "0" * 64}),
                *inventory.cards[1:],
            )
        }
    )
    with pytest.raises(ValueError):
        validate_inventory(changed, cache)
    source = cache / "normal" / PINS["normal"]["revision"][:12] / "data/test-00000-of-00001.parquet"
    source.write_bytes(b"changed")
    with pytest.raises(ValueError):
        validate_inventory(inventory, cache)


def test_missing_or_duplicate_card_and_source_pin_are_rejected(cache):
    inventory = build_pending_inventory(cache)
    for cards in (inventory.cards[:-1], inventory.cards[:-1] + (inventory.cards[0],)):
        changed = inventory.model_copy(update={"cards": cards})
        with pytest.raises(ValueError):
            validate_inventory(changed, cache)
    inventory.source_pins["normal"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        validate_inventory(inventory, cache)


def test_card_requires_public_revision_controls_findings_and_two_reviewers(cache):
    card = build_pending_inventory(cache).cards[0]
    assert "public_value_contract_missing" in admission_blockers(card)
    assert "requirements_missing" in admission_blockers(card)
    assert "known_findings_unresolved" in admission_blockers(card)
    assert "independent_review_missing" in admission_blockers(card)
    incomplete = card.model_copy(
        update={
            "public_contract_digest": "a" * 64,
            "requirements": (
                RequirementEvidence(
                    requirement_id="size",
                    public_clause="Return the requested circuit size as a declared value.",
                    oracle_case_digests=("b" * 64,),
                ),
            ),
        }
    )
    blockers = admission_blockers(incomplete)
    assert "independent_alternative_missing" in blockers
    assert "wrong_mutant_missing" in blockers
    assert "known_findings_unresolved" in blockers
    assert "independent_review_missing" in blockers

    reviewed = incomplete.model_copy(
        update={
            "requirements": (
                RequirementEvidence(
                    requirement_id="size",
                    public_clause="Return the requested circuit size as a declared value.",
                    oracle_case_digests=("b" * 64,),
                    independent_alternative_digests=("c" * 64,),
                    wrong_mutant_digests=("d" * 64,),
                ),
            ),
            "finding_resolutions": {
                hashlib.sha256(KNOWN_FINDINGS[0][0].encode()).hexdigest(): "e" * 64
            },
            "reviews": (
                ReviewAttestation(
                    reviewer_id="reviewer-a",
                    qualification_digest="f" * 64,
                    review_artifact_digest="1" * 64,
                    decision="approve",
                ),
                ReviewAttestation(
                    reviewer_id="reviewer-b",
                    qualification_digest="2" * 64,
                    review_artifact_digest="3" * 64,
                    decision="approve",
                ),
            ),
        }
    )
    assert admission_blockers(reviewed) == ()
    assert TaskCard.model_validate_json(reviewed.model_dump_json()).source_key == card.source_key


def test_duplicate_or_unqualified_reviewers_do_not_admit(cache):
    card = build_pending_inventory(cache).cards[0]
    reviewer = ReviewAttestation(
        reviewer_id="one",
        qualification_digest="a" * 64,
        review_artifact_digest="b" * 64,
        decision="approve",
    )
    duplicate = card.model_copy(update={"reviews": (reviewer, reviewer)})
    with pytest.raises(ValueError):
        admission_blockers(duplicate)
    unqualified = card.model_copy(
        update={
            "reviews": (
                reviewer,
                reviewer.model_copy(update={"reviewer_id": "two", "qualification_digest": None}),
            )
        }
    )
    assert "independent_review_missing" in admission_blockers(unqualified)
    reused_artifact = card.model_copy(
        update={
            "reviews": (
                reviewer,
                reviewer.model_copy(update={"reviewer_id": "two"}),
            )
        }
    )
    assert "independent_review_missing" in admission_blockers(reused_artifact)


def test_one_control_artifact_cannot_claim_opposite_outcomes():
    with pytest.raises(ValueError, match="disjoint"):
        RequirementEvidence(
            requirement_id="shape",
            public_clause="Return the declared shape",
            oracle_case_digests=("a" * 64,),
            wrong_mutant_digests=("a" * 64,),
        )


def test_cli_writes_exclusive_pending_inventory(cache, tmp_path, monkeypatch, capsys):
    output = tmp_path / "admission.json"
    monkeypatch.setattr(sys, "argv", ["graybench", "admission-inventory", str(cache), str(output)])
    main()
    result = json.loads(capsys.readouterr().out)
    saved = AdmissionInventory.model_validate_json(output.read_bytes())
    assert result["inventory_digest"] == saved.digest
    assert result["pending_cards"] == 302
    assert result["publication_eligible"] is False
    with pytest.raises(FileExistsError):
        main()
    monkeypatch.setattr(sys, "argv", ["graybench", "inventory", str(cache)])
    main()
    assert json.loads(capsys.readouterr().out)["task_count"] == 302


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Needs pinned parquet")
def test_real_pinned_inventory_has_302_pending_cards():
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    inventory = build_pending_inventory(cache)
    validate_inventory(inventory, cache)
    assert len(inventory.cards) == 302
    assert not inventory.publication_eligible

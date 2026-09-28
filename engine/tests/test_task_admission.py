import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from test_native_cohort import cache as _synthetic_cache

from graybench.cli import main
from graybench.datasets import EXTERNAL_IDS, KNOWN_FINDINGS, PINS, load_suite
from graybench.judge import Judgment
from graybench.oracle_review import inspect_oracle_review, run_review
from graybench.task_admission import (
    AdmissionInventory,
    RequirementEvidence,
    ReviewAttestation,
    TaskCard,
    admission_blockers,
    audit_control_coverage,
    build_pending_inventory,
    validate_inventory,
)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    return _synthetic_cache.__wrapped__(tmp_path, monkeypatch)


def test_pending_inventory_contains_exact_pinned_302_and_no_admission(cache):
    inventory = build_pending_inventory(cache)
    assert inventory.schema_version == "2"
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


def test_v2_admission_inventory_survives_engine_changes_but_v1_does_not(cache, monkeypatch):
    inventory = build_pending_inventory(cache)
    old = inventory.model_copy(update={"schema_version": "1"})
    legacy = old.model_dump(mode="json")
    legacy.pop("schema_version")
    parsed_legacy = AdmissionInventory.model_validate_json(json.dumps(legacy))
    assert parsed_legacy.schema_version == "1"
    monkeypatch.setattr("graybench.task_admission.source_manifest", lambda: {"digest": "f" * 64})
    validate_inventory(inventory, cache)
    with pytest.raises(ValueError, match="engine source changed"):
        validate_inventory(old, cache)
    with pytest.raises(ValueError, match="engine source changed"):
        validate_inventory(parsed_legacy, cache)


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
    rejected = reviewed.model_copy(
        update={
            "reviews": reviewed.reviews
            + (ReviewAttestation(reviewer_id="reviewer-c", decision="reject"),)
        }
    )
    assert "review_rejection_unresolved" in admission_blockers(rejected)


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


def test_admission_control_audit_links_verified_cases_without_admitting_tasks(
    cache, tmp_path, monkeypatch, capsys
):
    class ProbeJudge:
        def evaluate(self, _task, completion):
            outcome = "pass" if "QuantumCircuit(3)" not in completion else "fail"
            return Judgment(outcome, "0" * 64, {})

    inventory = build_pending_inventory(cache)
    task = load_suite("normal", cache)[0]
    review = tmp_path / "review.jsonl"
    run_review((task,), ProbeJudge(), review)
    report = audit_control_coverage(inventory, cache, (review,))
    assert report["control_count"] == 3
    assert report["covered_task_count"] == 1
    assert report["uncovered_task_count"] == 301
    assert report["unexpected_outcome_count"] == 0
    assert report["publication_eligible"] is False
    first = report["tasks"][0]
    assert first["task_key"] == "normal/qiskitHumanEval/0"
    assert first["controls"][0]["case_digest"]
    assert all(not row["controls"] for row in report["tasks"][1:])

    inventory_file = tmp_path / "inventory.json"
    inventory_file.write_text(inventory.model_dump_json())
    output = tmp_path / "audit.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "admission-control-audit",
            str(inventory_file),
            str(cache),
            str(output),
            str(review),
        ],
    )
    main()
    cli = json.loads(capsys.readouterr().out)
    assert cli["report_digest"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert cli["covered_task_count"] == 1
    with pytest.raises(FileExistsError):
        main()


def test_admission_control_audit_rejects_duplicate_or_unpinned_evidence(cache, tmp_path):
    class Judge:
        def evaluate(self, _task, completion):
            return Judgment("pass", "0" * 64, {})

    inventory = build_pending_inventory(cache)
    review = tmp_path / "review.jsonl"
    run_review((load_suite("normal", cache)[0],), Judge(), review)
    report = audit_control_coverage(inventory, cache, (review,))
    assert report["unexpected_outcome_count"] == 1
    with pytest.raises(ValueError, match="Duplicate"):
        audit_control_coverage(inventory, cache, (review, review))
    changed = inventory.model_copy(update={"source_pins": {"normal": {}, "hard": {}}})
    with pytest.raises(ValueError):
        audit_control_coverage(changed, cache, (review,))


def test_admission_control_audit_separates_wrong_passes_rejections_and_errors(cache, tmp_path):
    class MixedJudge:
        def evaluate(self, _task, completion):
            if "QuantumCircuit(3)" in completion:
                outcome = "pass"
            elif "QuantumRegister" in completion:
                outcome = "fail"
            else:
                outcome = "timeout"
            return Judgment(outcome, "0" * 64, {})

    inventory = build_pending_inventory(cache)
    review = tmp_path / "mixed.jsonl"
    run_review((load_suite("normal", cache)[0],), MixedJudge(), review)
    report = audit_control_coverage(inventory, cache, (review,))
    assert report["unexpected_outcome_count"] == 3
    assert report["false_pass_count"] == 1
    assert report["false_rejection_count"] == 1
    assert report["other_mismatch_count"] == 1


def test_admission_audit_links_requirement_claims_to_observed_controls(cache, tmp_path):
    class ProbeJudge:
        def evaluate(self, _task, completion):
            outcome = "fail" if "QuantumCircuit(3)" in completion else "pass"
            return Judgment(outcome, "0" * 64, {})

    inventory = build_pending_inventory(cache)
    review = tmp_path / "review.jsonl"
    run_review((load_suite("normal", cache)[0],), ProbeJudge(), review)
    controls = inspect_oracle_review(review, cache)["controls"]
    by_name = {item["case_key"].rsplit("/", 1)[1]: item for item in controls}
    requirement = RequirementEvidence(
        requirement_id="size",
        public_clause="Return a circuit of the requested size.",
        oracle_case_digests=("a" * 64,),
        independent_alternative_digests=(by_name["register-alternative"]["case_digest"],),
        wrong_mutant_digests=(by_name["constant-three"]["case_digest"],),
    )
    card = inventory.cards[0].model_copy(update={"requirements": (requirement,)})
    inventory = inventory.model_copy(update={"cards": (card, *inventory.cards[1:])})

    report = audit_control_coverage(inventory, cache, (review,))
    assert report["schema_version"] == "2"
    links = {item["role"]: item for item in report["tasks"][0]["evidence_links"]}
    assert links["oracle_case"]["status"] == "unverified_fixture"
    assert links["independent_alternative"]["status"] == "matching_local_observation"
    assert links["wrong_mutant"]["status"] == "matching_local_observation"
    assert (
        links["wrong_mutant"]["observations"][0]["artifact_file_sha256"]
        == report["artifacts"][0]["file_sha256"]
    )
    assert report["publication_eligible"] is False


def test_admission_audit_flags_missing_wrong_role_and_conflicting_outcomes(cache, tmp_path):
    class ExpectedJudge:
        def evaluate(self, _task, completion):
            return Judgment("fail" if "QuantumCircuit(3)" in completion else "pass", "0" * 64, {})

    class AlwaysPassJudge:
        def evaluate(self, _task, _completion):
            return Judgment("pass", "1" * 64, {})

    inventory = build_pending_inventory(cache)
    task = load_suite("normal", cache)[0]
    good = tmp_path / "good.jsonl"
    bad = tmp_path / "bad.jsonl"
    run_review((task,), ExpectedJudge(), good)
    run_review((task,), AlwaysPassJudge(), bad)
    controls = inspect_oracle_review(good, cache)["controls"]
    by_name = {item["case_key"].rsplit("/", 1)[1]: item for item in controls}
    requirement = RequirementEvidence(
        requirement_id="size",
        public_clause="Return a circuit of the requested size.",
        independent_alternative_digests=("b" * 64,),
        wrong_mutant_digests=(
            by_name["gated-alternative"]["case_digest"],
            by_name["constant-three"]["case_digest"],
        ),
    )
    card = inventory.cards[0].model_copy(update={"requirements": (requirement,)})
    inventory = inventory.model_copy(update={"cards": (card, *inventory.cards[1:])})

    report = audit_control_coverage(inventory, cache, (good, bad))
    links = {item["digest"]: item for item in report["tasks"][0]["evidence_links"]}
    assert links["b" * 64]["status"] == "missing_local_observation"
    assert links[by_name["gated-alternative"]["case_digest"]]["status"] == (
        "unexpected_local_outcome"
    )
    conflicting = links[by_name["constant-three"]["case_digest"]]
    assert conflicting["status"] == "unexpected_local_outcome"
    assert {item["actual"] for item in conflicting["observations"]} == {"pass", "fail"}


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Needs pinned parquet")
def test_real_pinned_inventory_has_302_pending_cards():
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    inventory = build_pending_inventory(cache)
    validate_inventory(inventory, cache)
    assert len(inventory.cards) == 302
    assert not inventory.publication_eligible

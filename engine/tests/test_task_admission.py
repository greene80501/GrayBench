import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from test_native_cohort import cache as _synthetic_cache

from graybench import datasets
from graybench import task_admission as admission
from graybench.cli import main
from graybench.datasets import EXTERNAL_IDS, KNOWN_FINDINGS, PINS, load_suite
from graybench.identity import identity
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
    assert inventory.schema_version == "3"
    assert inventory.track == "graybench-protected-semantic-v1"
    assert len(inventory.cards) == 302
    assert inventory.cards[0].source_key == "normal/qiskitHumanEval/0"
    assert inventory.cards[151].source_key == "hard/qiskitHumanEval/0"
    assert inventory.cards[-1].source_key == "hard/qiskitHumanEval/150"
    assert inventory.source_pins == PINS
    assert sum(card.external_service for card in inventory.cards) == 16
    assert all(card.public_contract_digest is None for card in inventory.cards)
    assert "protected_judge_digest" not in inventory.cards[0].model_dump()
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
    for suite in ("normal", "hard"):
        card = next(
            card for card in inventory.cards if card.source_key == f"{suite}/qiskitHumanEval/62"
        )
        assert card.known_findings == tuple(KNOWN_FINDINGS[62])
        assert any(
            "omits valid inputs" in finding and "124 cases" in finding
            for finding in card.known_findings
        )
        assert "known_findings_unresolved" in admission_blockers(card)
    admission.require_current_finding_registry(inventory)
    validate_inventory(inventory, cache)


def test_v2_historical_findings_verify_but_new_registry_is_required_for_current_use(cache):
    current = build_pending_inventory(cache)
    legacy_cards = tuple(
        card.model_copy(
            update={
                "known_findings": tuple(
                    datasets.KNOWN_FINDINGS_V2.get(int(card.source_key.rsplit("/", 1)[1]), ())
                )
            }
        )
        for card in current.cards
    )
    legacy = current.model_copy(
        update={
            "schema_version": "2",
            "finding_registry": {},
            "finding_registry_digest": None,
            "cards": legacy_cards,
        }
    )
    validate_inventory(legacy, cache)
    with pytest.raises(ValueError, match="current finding registry"):
        admission.require_current_finding_registry(legacy)
    omitted = current.model_copy(
        update={
            "cards": tuple(
                card.model_copy(update={"known_findings": ()})
                if card.source_key == "normal/qiskitHumanEval/62"
                else card
                for card in current.cards
            )
        }
    )
    with pytest.raises(ValueError, match="finding registry"):
        validate_inventory(omitted, cache)
    with pytest.raises(ValueError, match="current finding registry"):
        admission.require_current_finding_registry(omitted)


def test_current_finding_mutation_cannot_change_frozen_v2_registry():
    historical = tuple(datasets.KNOWN_FINDINGS_V2[0])
    datasets.KNOWN_FINDINGS[0].append("New current finding")
    try:
        assert tuple(datasets.KNOWN_FINDINGS_V2[0]) == historical
    finally:
        datasets.KNOWN_FINDINGS[0].pop()


def test_v3_finding_snapshot_remains_readable_after_new_registry_change(cache, monkeypatch):
    inventory = build_pending_inventory(cache)
    expanded = {**KNOWN_FINDINGS, 100: ["Newly discovered finding"]}
    monkeypatch.setattr("graybench.task_admission.KNOWN_FINDINGS", expanded)
    validate_inventory(inventory, cache)
    with pytest.raises(ValueError, match="current finding registry"):
        admission.require_current_finding_registry(inventory)


def test_refresh_finding_registry_preserves_review_work_and_adds_task62(cache):
    current = build_pending_inventory(cache)
    source_cards = []
    for card in current.cards:
        number = int(card.source_key.rsplit("/", 1)[1])
        source_cards.append(
            card.model_copy(
                update={
                    "known_findings": tuple(datasets.KNOWN_FINDINGS_V2.get(number, ())),
                    "public_contract_digest": (
                        "a" * 64 if card.source_key == "normal/qiskitHumanEval/2" else None
                    ),
                }
            )
        )
    historical = current.model_copy(
        update={
            "schema_version": "2",
            "finding_registry": {},
            "finding_registry_digest": None,
            "cards": tuple(source_cards),
        }
    )
    refreshed = admission.refresh_finding_registry(historical, cache)
    validate_inventory(refreshed, cache)
    admission.require_current_finding_registry(refreshed)
    assert refreshed.schema_version == "3"
    assert refreshed.cards[2].public_contract_digest == "a" * 64
    assert historical.cards[2].public_contract_digest == "a" * 64
    for suite in ("normal", "hard"):
        key = f"{suite}/qiskitHumanEval/62"
        card = next(card for card in refreshed.cards if card.source_key == key)
        assert card.known_findings == tuple(KNOWN_FINDINGS[62])
        assert "known_findings_unresolved" in admission_blockers(card)


def test_v3_admission_inventory_survives_engine_changes_but_v1_does_not(cache, monkeypatch):
    inventory = build_pending_inventory(cache)
    old = inventory.model_copy(
        update={"schema_version": "1", "finding_registry": {}, "finding_registry_digest": None}
    )
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
    assert "protected_judge_missing" in blockers

    reviewed = incomplete.model_copy(
        update={
            "protected_judge_digest": "4" * 64,
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


def test_cli_refreshes_historical_findings_without_overwriting(
    cache, tmp_path, monkeypatch, capsys
):
    current = build_pending_inventory(cache)
    historical = current.model_copy(
        update={
            "schema_version": "2",
            "finding_registry": {},
            "finding_registry_digest": None,
            "cards": tuple(
                card.model_copy(
                    update={
                        "known_findings": tuple(
                            datasets.KNOWN_FINDINGS_V2.get(
                                int(card.source_key.rsplit("/", 1)[1]), ()
                            )
                        )
                    }
                )
                for card in current.cards
            ),
        }
    )
    source = tmp_path / "historical.json"
    source.write_text(historical.model_dump_json(), encoding="utf-8")
    output = tmp_path / "refreshed.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["graybench", "admission-refresh-findings", str(source), str(cache), str(output)],
    )
    main()
    result = json.loads(capsys.readouterr().out)
    saved = AdmissionInventory.model_validate_json(output.read_bytes())
    assert saved.schema_version == "3"
    assert result["inventory_digest"] == saved.digest
    assert result["new_finding_card_count"] == 4
    assert all(
        "known_findings_unresolved" in admission_blockers(saved.cards[offset + 41])
        for offset in (0, 151)
    )
    assert result["publication_eligible"] is False
    with pytest.raises(FileExistsError):
        main()


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
    task = load_suite("normal", cache)[0]
    manifest = {
        "track": "graybench-protected-semantic-v1",
        "source_task_digest": task.digest,
        "public_contract_digest": "c" * 64,
    }

    class ProbeJudge:
        def evaluate(self, _task, completion):
            outcome = "fail" if "QuantumCircuit(3)" in completion else "pass"
            return Judgment(outcome, identity(manifest), {"manifest": manifest})

    inventory = build_pending_inventory(cache)
    review = tmp_path / "review.jsonl"
    run_review((task,), ProbeJudge(), review)
    controls = inspect_oracle_review(review, cache)["controls"]
    by_name = {item["case_key"].rsplit("/", 1)[1]: item for item in controls}
    requirement = RequirementEvidence(
        requirement_id="size",
        public_clause="Return a circuit of the requested size.",
        oracle_case_digests=("a" * 64,),
        independent_alternative_digests=(by_name["register-alternative"]["case_digest"],),
        wrong_mutant_digests=(by_name["constant-three"]["case_digest"],),
    )
    card = inventory.cards[0].model_copy(
        update={
            "public_contract_digest": "c" * 64,
            "protected_judge_digest": identity(manifest),
            "requirements": (requirement,),
        }
    )
    inventory = inventory.model_copy(update={"cards": (card, *inventory.cards[1:])})

    report = audit_control_coverage(inventory, cache, (review,))
    assert report["schema_version"] == "5"
    links = {item["role"]: item for item in report["tasks"][0]["evidence_links"]}
    assert links["oracle_case"]["status"] == "unverified_fixture"
    assert links["independent_alternative"]["status"] == "unqualified_judge_condition"
    assert links["wrong_mutant"]["status"] == "unqualified_judge_condition"

    declared = tmp_path / "declared.jsonl"
    run_review(
        (task,),
        ProbeJudge(),
        declared,
        declared_judges={"normal/qiskitHumanEval/0": manifest},
    )
    report = audit_control_coverage(inventory, cache, (review, declared))
    links = {item["role"]: item for item in report["tasks"][0]["evidence_links"]}
    assert links["independent_alternative"]["status"] == "matching_local_observation"
    assert links["wrong_mutant"]["status"] == "matching_local_observation"
    assert links["wrong_mutant"]["declared_frozen_judge_observation_count"] == 1
    assert report["publication_eligible"] is False


def test_admission_audit_does_not_credit_upstream_or_unbound_controls(cache, tmp_path):
    class ConditionJudge:
        def __init__(self, manifest, *, force_pass=False):
            self.manifest = manifest
            self.force_pass = force_pass

        def evaluate(self, _task, completion):
            outcome = "pass" if self.force_pass or "QuantumCircuit(3)" not in completion else "fail"
            return Judgment(outcome, identity(self.manifest), {"manifest": self.manifest})

    inventory = build_pending_inventory(cache)
    task = load_suite("normal", cache)[0]
    upstream = tmp_path / "upstream.jsonl"
    wrong_contract = tmp_path / "wrong-contract.jsonl"
    wrong_oracle = tmp_path / "wrong-oracle.jsonl"
    matching_manifest = {
        "track": "graybench-protected-semantic-v1",
        "source_task_digest": task.digest,
        "public_contract_digest": "c" * 64,
        "oracle": "all-layouts-v2",
    }
    run_review(
        (task,), ConditionJudge({"protocol": "upstream-proxy-v1"}, force_pass=True), upstream
    )
    run_review(
        (task,),
        ConditionJudge(
            {
                "track": "graybench-protected-semantic-v1",
                "source_task_digest": task.digest,
                "public_contract_digest": "d" * 64,
            }
        ),
        wrong_contract,
        declared_judges={
            "normal/qiskitHumanEval/0": {
                "track": "graybench-protected-semantic-v1",
                "source_task_digest": task.digest,
                "public_contract_digest": "d" * 64,
            }
        },
    )
    run_review(
        (task,),
        ConditionJudge({**matching_manifest, "oracle": "three-layouts-v1"}),
        wrong_oracle,
        declared_judges={
            "normal/qiskitHumanEval/0": {**matching_manifest, "oracle": "three-layouts-v1"}
        },
    )
    control = inspect_oracle_review(upstream, cache)["controls"][0]
    card = inventory.cards[0].model_copy(
        update={
            "public_contract_digest": "c" * 64,
            "protected_judge_digest": identity(matching_manifest),
            "requirements": (
                RequirementEvidence(
                    requirement_id="size",
                    public_clause="Return the requested size.",
                    wrong_mutant_digests=(control["case_digest"],),
                ),
            ),
        }
    )
    inventory = inventory.model_copy(update={"cards": (card, *inventory.cards[1:])})
    report = audit_control_coverage(inventory, cache, (upstream, wrong_contract, wrong_oracle))
    link = report["tasks"][0]["evidence_links"][0]
    assert link["status"] == "unqualified_judge_condition"
    assert {item["judge_track"] for item in link["observations"]} == {
        "upstream-proxy-v1",
        "graybench-protected-semantic-v1",
    }
    assert report["declared_frozen_judge_control_count"] == 0
    assert report["false_pass_count"] == 1

    matching = tmp_path / "matching.jsonl"
    run_review(
        (task,),
        ConditionJudge(matching_manifest),
        matching,
        declared_judges={"normal/qiskitHumanEval/0": matching_manifest},
    )
    combined = audit_control_coverage(
        inventory, cache, (upstream, wrong_contract, wrong_oracle, matching)
    )
    linked = combined["tasks"][0]["evidence_links"][0]
    assert linked["status"] == "matching_local_observation"
    assert linked["declared_frozen_judge_observation_count"] == 1
    assert len(linked["observations"]) == 4
    assert combined["declared_frozen_judge_control_count"] == 3
    assert combined["false_pass_count"] == 1


def test_admission_audit_rejects_claimed_manifest_with_wrong_judge_digest(cache, tmp_path):
    class ForgedJudge:
        def evaluate(self, _task, _completion):
            return Judgment("pass", "0" * 64, {"manifest": {"track": "fake"}})

    inventory = build_pending_inventory(cache)
    review = tmp_path / "forged.jsonl"
    run_review((load_suite("normal", cache)[0],), ForgedJudge(), review)
    with pytest.raises(ValueError, match="manifest digest"):
        audit_control_coverage(inventory, cache, (review,))


def test_admission_audit_flags_missing_wrong_role_and_conflicting_outcomes(cache, tmp_path):
    task = load_suite("normal", cache)[0]
    manifest = {
        "track": "graybench-protected-semantic-v1",
        "source_task_digest": task.digest,
        "public_contract_digest": "c" * 64,
    }

    class ExpectedJudge:
        def evaluate(self, _task, completion):
            return Judgment(
                "fail" if "QuantumCircuit(3)" in completion else "pass",
                identity(manifest),
                {"manifest": manifest},
            )

    class AlwaysPassJudge:
        def evaluate(self, _task, _completion):
            return Judgment("pass", identity(manifest), {"manifest": manifest})

    inventory = build_pending_inventory(cache)
    good = tmp_path / "good.jsonl"
    bad = tmp_path / "bad.jsonl"
    run_review(
        (task,),
        ExpectedJudge(),
        good,
        declared_judges={"normal/qiskitHumanEval/0": manifest},
    )
    run_review(
        (task,),
        AlwaysPassJudge(),
        bad,
        declared_judges={"normal/qiskitHumanEval/0": manifest},
    )
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
    card = inventory.cards[0].model_copy(
        update={
            "public_contract_digest": "c" * 64,
            "protected_judge_digest": identity(manifest),
            "requirements": (requirement,),
        }
    )
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

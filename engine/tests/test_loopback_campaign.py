"""Real socket-to-ledger regression; authored execution replaces Docker only."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from loopback_campaign_support import IMAGE, SECRET, AuthoredRunner, answer, endpoint

from graybench.contracts import ModelSpec
from graybench.datasets import load_suite
from graybench.identity import canonical
from graybench.ledger import Ledger
from graybench.model_discovery import observe_run
from graybench.protected_campaign import (
    ProtectedCampaign,
    ProtectedCampaignSetup,
    build_protected_setup,
    freeze_protected_cohort,
)
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task2 import task2_value_task
from graybench.providers import BUILTINS
from graybench.transport import Transport

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")


@pytest.mark.skipif(not CACHE, reason="Exact pinned cache required")
@pytest.mark.parametrize("name", BUILTINS)
@pytest.mark.parametrize("suite", ["normal", "hard"])
@pytest.mark.parametrize("scenario", ["returned", "server-error", "redirect"])
def test_real_http_campaign_restart_binds_answers_and_never_replays_uncertain_delivery(
    name, suite, scenario, tmp_path, monkeypatch
):
    monkeypatch.setenv("GRAYBENCH_TEST_LOOPBACK_CREDENTIAL", SECRET)
    monkeypatch.setattr(
        ProtectedCampaignSetup,
        "judge",
        lambda self, docker="docker": ProtectedSemanticJudge(AuthoredRunner()),
    )
    pinned = load_suite(suite, Path(CACHE))[2]
    task = task2_value_task(pinned)
    path = tmp_path / "campaign.sqlite"
    with endpoint(name, suite, scenario) as (url, generation_path, records):
        model = ModelSpec(
            adapter=name,
            model="fixture",
            base_url=url,
            credential_env="GRAYBENCH_TEST_LOOPBACK_CREDENTIAL",
            credential_scope_id="fixture/loopback",
            discovery_policy="unverified_development"
            if name == "openai-compatible-chat"
            else "required",
            discovery_exception_reason="Test fixture has no metadata interface"
            if name == "openai-compatible-chat"
            else None,
        )
        cohort = freeze_protected_cohort(
            (task,),
            cache=Path(CACHE),
            suite=suite,
            image=IMAGE,
            label="loopback wiring only",
            excluded={
                f"{suite}/qiskitHumanEval/{n}": "out_of_scope_development"
                for n in range(151)
                if n != 2
            },
        )
        frozen = build_protected_setup(
            "loopback wiring", model, cohort, (task,), cache=Path(CACHE), repeats=2
        )
        ledger = Ledger(path)
        transport = Transport(model, timeout_seconds=5)
        try:
            run = ledger.create_run(frozen.protocol, {"setup": frozen.model_dump(mode="json")})
            assert observe_run(ledger, run, transport)["status"] != "unresolved"
            campaign = ProtectedCampaign(ledger, run, frozen, Path(CACHE), transport)
            first = campaign.step()
            assert first["state"] == "dispatched"
            assert first["delivery"] == ("returned" if scenario == "returned" else "ambiguous")
        finally:
            ledger.close()
            transport.close()

        # Reconstruct from durable setup rather than reuse the original objects.
        ledger = Ledger(path)
        frozen = ProtectedCampaignSetup.model_validate_json(canonical(ledger.context(run)["setup"]))
        transport = Transport(frozen.protocol.model, timeout_seconds=5)
        try:
            campaign = ProtectedCampaign(ledger, run, frozen, Path(CACHE), transport)
            if scenario == "returned":
                states = [campaign.step() for _ in range(4)]
                assert [s["state"] for s in states] == [
                    "judged",
                    "dispatched",
                    "judged",
                    "judgments_complete",
                ]
                assert [s["outcome"] for s in states if s["state"] == "judged"] == ["pass", "fail"]
                assert campaign.step()["state"] == "judgments_complete"
            else:
                assert campaign.step() == {"state": "stopped", "reason": "unresolved_delivery"}
                assert campaign.step() == {"state": "stopped", "reason": "unresolved_delivery"}
            report = ledger.summary(run)
            assert report["publication_eligible"] is False
            assert report["ledger_integrity"]["integrity"] == "verified"
            assert report["pass_at_1"] == (0.5 if scenario == "returned" else None)
            assert report["judgment_evidence_binding"] == {
                "bound": 2 if scenario == "returned" else 0,
                "legacy_unbound": 0,
            }
            count = 2 if scenario == "returned" else 1
            assert report["request_evidence_binding"] == {"bound": count, "unbound": 0}
            deliveries = [
                ledger.blob(row[0]) for row in ledger.db.execute("SELECT evidence FROM deliveries")
            ]
            requests = [r for r in records if r["path"] == generation_path]
            assert len(requests) == len(deliveries) == count
            assert all(r["auth_ok"] for r in records)
            assert all(r["path"] != "/forbidden" for r in records)
            for request, delivery in zip(requests, deliveries, strict=True):
                public = json.loads(request["body"])
                assert request["body"] == canonical(public)
                assert json.dumps(task.contract.public.prompt)[1:-1] in json.dumps(public)
                assert json.dumps(pinned.upstream_test)[1:-1] not in json.dumps(public)
                assert json.dumps(pinned.canonical_solution)[1:-1] not in json.dumps(public)
                assert (
                    delivery["request_content_sha256"]
                    == hashlib.sha256(request["body"]).hexdigest()
                )
                assert delivery["response_capture_version"] == "encoded_entity_v2"
                assert delivery["wire_sha256"] == hashlib.sha256(request["wire"]).hexdigest()
                assert (
                    delivery["decoded_body_sha256"]
                    == hashlib.sha256(request["decoded"]).hexdigest()
                )
                assert delivery["wire_bytes"] == len(request["wire"])
                assert delivery["response_bytes"] == len(request["decoded"])
            assert ledger.verify()["integrity"] == "verified"
            blobs = "\n".join(str(row[0]) for row in ledger.db.execute("SELECT content FROM blobs"))
            assert SECRET not in blobs
            if scenario == "returned":
                texts = [
                    ledger.blob(row[0])["text"]
                    for row in ledger.db.execute("SELECT content FROM generations ORDER BY rowid")
                ]
                assert texts == [answer(suite, True), answer(suite, False)]
        finally:
            ledger.close()
            transport.close()

"""Protocol choice must be frozen and distinguishable from historical v3."""

import json
import sys

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.cli import main
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import validate_cohort
from graybench.evaluation_recipes import recipe_judge
from graybench.graph_runtime import GRAPH_FILES
from graybench.ledger import StateError

IMAGE = "sha256:" + "0" * 64


def fixture(public):
    return JudgeTask(
        public=public,
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="def check(candidate):\n    assert candidate(1) == 1",
        upstream_difficulty="fixture",
    )


def test_graph_recipe_is_explicit_and_source_bound(model, task):
    item = fixture(task)
    old = build_setup("old", model, (item,), IMAGE)
    new = build_setup("new", model, (item,), IMAGE, evaluation_recipe="upstream-graph-v4")
    assert new.protocol.request_digests == old.protocol.request_digests
    assert new.protocol.judge_digest != old.protocol.judge_digest
    restored = CampaignSetup.model_validate_json(new.model_dump_json())
    assert restored.judge().protocol == 4
    validate_cohort(new.protocol, (item,), restored.judge())
    with pytest.raises(StateError):
        validate_cohort(new.protocol, (item,), old.judge())
    payload, manifest = restored.judge().configuration(item)
    assert set(GRAPH_FILES) <= set(manifest["files"])
    assert manifest["protocol"] == "upstream-graph-v4"
    assert "graph_session" not in payload
    assert manifest["graph_session_policy"] == "random-per-attempt-v1"
    assert "PRIVATE_REFERENCE" not in new.model_dump_json()


def test_explicit_graph_recipe_cannot_be_overridden_to_v3():
    with pytest.raises(ValueError):
        recipe_judge("upstream-graph-v4", image=IMAGE, protocol=3)


def test_delta_recipe_roundtrip_preserves_transport_and_model_requests(model, task):
    item = fixture(task)
    full = build_setup("full", model, (item,), IMAGE, evaluation_recipe="upstream-graph-v4")
    delta = build_setup("delta", model, (item,), IMAGE, evaluation_recipe="upstream-graph-delta-v1")
    restored = CampaignSetup.model_validate_json(delta.model_dump_json())
    judge = restored.judge()
    assert judge.graph_transport["mode"] == "delta-v1"
    assert delta.protocol.request_digests == full.protocol.request_digests
    assert delta.protocol.judge_digest != full.protocol.judge_digest
    validate_cohort(restored.protocol, (item,), judge)
    with pytest.raises(StateError):
        validate_cohort(restored.protocol, (item,), full.judge())
    with pytest.raises(ValueError):
        recipe_judge("upstream-graph-delta-v1", image=IMAGE, graph_transport="snapshot-v1")


def test_reference_scan_cli_selects_graph_protocol(task, monkeypatch, capsys, tmp_path):
    item = fixture(task)
    monkeypatch.setattr(
        "graybench.cli.load_suite", lambda suite, _: (item,) if suite == "hard" else ()
    )
    monkeypatch.setattr(
        "graybench.cli.run_reference_scan",
        lambda tasks, judge, path, **kwargs: {"protocol": judge.protocol},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "reference-scan",
            str(tmp_path),
            str(tmp_path / "scan.jsonl"),
            "--image",
            IMAGE,
            "--bridge-protocol",
            "4",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["protocol"] == 4

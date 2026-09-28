"""Protected development campaigns freeze revisions, exclusions, and judgments."""

import json
import os
import sys
from pathlib import Path

import httpx
import pytest

from graybench.cli import main
from graybench.comparison import ComparisonPlan, validate_plan
from graybench.contracts import ModelSpec, Protocol, RetryPolicy
from graybench.datasets import load_suite
from graybench.ledger import StateError
from graybench.protected_campaign import (
    ProtectedCampaign,
    ProtectedCampaignSetup,
    build_protected_setup,
    freeze_protected_cohort,
    validate_protected_cohort,
)
from graybench.protected_task2 import task2_value_task
from graybench.protected_task20 import task20_value_task
from graybench.provenance import source_manifest
from graybench.transport import Transport

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "a" * 64)
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
MODEL = ModelSpec(adapter="ollama", model="fixture", base_url="http://localhost:11434")


def setup(suite="normal"):
    if not CACHE:
        pytest.skip("Pinned source cache required")
    cache = Path(CACHE)
    pinned = next(
        source
        for source in load_suite(suite, cache)
        if source.public.task_id == "qiskitHumanEval/20"
    )
    task = task20_value_task(pinned)
    excluded = {
        f"{suite}/qiskitHumanEval/{number}": "unreviewed_or_unsupported"
        for number in range(151)
        if number != 20
    }
    cohort = freeze_protected_cohort(
        (task,),
        cache=cache,
        suite=suite,
        image=IMAGE,
        label="task20 development",
        excluded=excluded,
    )
    return build_protected_setup("fixture", MODEL, cohort, (task,), cache=cache)


def two_task_setup(suite="normal"):
    if not CACHE:
        pytest.skip("Pinned source cache required")
    cache = Path(CACHE)
    pinned = {
        task.public.task_id: task
        for task in load_suite(suite, cache)
        if task.public.task_id in {"qiskitHumanEval/2", "qiskitHumanEval/20"}
    }
    tasks = (
        task2_value_task(pinned["qiskitHumanEval/2"]),
        task20_value_task(pinned["qiskitHumanEval/20"]),
    )
    excluded = {
        f"{suite}/qiskitHumanEval/{number}": "unreviewed_or_unsupported"
        for number in range(151)
        if number not in {2, 20}
    }
    cohort = freeze_protected_cohort(
        tasks,
        cache=cache,
        suite=suite,
        image=IMAGE,
        label="two value tasks",
        excluded=excluded,
    )
    return build_protected_setup("two task fixture", MODEL, cohort, tasks, cache=cache)


def direct_solution():
    return (
        "def ghz_amplitudes(layout):\n"
        "    import math\n"
        "    v = [[0.0,0.0] for _ in range(128)]\n"
        "    v[0][0] = v[sum(1 << wire for wire in layout)][0] = 1/math.sqrt(2)\n"
        "    return v\n"
    )


def handler(request):
    discovery = {
        "/api/version": {"version": "fixture"},
        "/api/tags": {"models": [{"name": "fixture", "digest": "a" * 64}]},
        "/api/show": {"model_info": {"architecture": "fixture"}},
        "/api/ps": {"models": []},
    }
    if request.url.path in discovery:
        return httpx.Response(200, json=discovery[request.url.path])
    return httpx.Response(
        200,
        json={
            "model": "fixture",
            "done": True,
            "message": {"role": "assistant", "content": direct_solution()},
        },
    )


def test_protected_protocol_rejects_mixed_suite_and_unbound_population():
    with pytest.raises(ValueError):
        Protocol(
            schema_version="3.3",
            name="bad",
            track="graybench-protected-semantic-v1",
            dataset_digest="1" * 64,
            task_keys=("normal/qiskitHumanEval/20", "hard/qiskitHumanEval/20"),
            request_digests={
                "normal/qiskitHumanEval/20": "2" * 64,
                "hard/qiskitHumanEval/20": "2" * 64,
            },
            model_observation_timing={"max_pre_age_seconds": 30, "max_post_delay_seconds": 120},
            model=MODEL,
            generation_code_digest="3" * 64,
            runtime_digest="4" * 64,
            judge_digest="5" * 64,
            analysis_digest="6" * 64,
        )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_frozen_protected_cohort_has_151_record_inventory_and_development_report(ledger):
    frozen = setup()
    assert isinstance(frozen, ProtectedCampaignSetup)
    assert frozen.protocol.track == "graybench-protected-semantic-v1"
    assert frozen.protocol.protected_suite == "normal"
    assert frozen.protocol.protected_population == "custom_development"
    assert frozen.protocol.retry.max_attempts == 1
    assert frozen.protocol.retry.statuses == ()
    assert len(frozen.cohort.excluded) == 150
    assert frozen.cohort.task_keys == ("normal/qiskitHumanEval/20",)
    run = ledger.create_run(frozen.protocol)
    report = ledger.summary(run)
    assert report["suite"] == "normal"
    assert report["population"] == "custom_development"
    assert report["denominator"] == 1
    assert report["excluded"] == frozen.cohort.excluded
    assert report["publication_eligible"] is False
    assert report["pass_at_1"] is None
    assert setup("hard").protocol.digest != frozen.protocol.digest


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_two_task_cohort_freezes_pinned_order_and_rejects_forged_revision(suite):
    frozen = two_task_setup(suite)
    assert frozen.cohort.task_keys == (
        f"{suite}/qiskitHumanEval/2",
        f"{suite}/qiskitHumanEval/20",
    )
    assert len(frozen.cohort.excluded) == 149
    assert frozen.protocol.protected_suite == suite
    assert frozen.protocol.retry.max_attempts == 1
    assert frozen.protocol.judge_digest != setup(suite).protocol.judge_digest
    assert frozen.cohort.population == "custom_development"
    forged = frozen.tasks[0].model_copy(update={"oracle": frozen.tasks[1].oracle})
    with pytest.raises((StateError, ValueError)):
        validate_protected_cohort(frozen.cohort, (forged, frozen.tasks[1]), cache=Path(CACHE))


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_cli_plan_supports_both_value_tasks_without_mixing_suites(tmp_path, monkeypatch, capsys):
    model_path = tmp_path / "model.json"
    setup_path = tmp_path / "setup.json"
    model_path.write_text(MODEL.model_dump_json(), encoding="utf-8")
    argv = [
        "graybench",
        "protected-plan",
        str(model_path),
        CACHE,
        str(setup_path),
        "--name",
        "both",
        "--label",
        "two-value-development",
        "--suite",
        "normal",
        "--task",
        "normal/qiskitHumanEval/20",
        "--task",
        "normal/qiskitHumanEval/2",
        "--image",
        IMAGE,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["planned_samples"] == 2
    planned = ProtectedCampaignSetup.model_validate_json(setup_path.read_bytes())
    assert planned.cohort.task_keys == (
        "normal/qiskitHumanEval/2",
        "normal/qiskitHumanEval/20",
    )
    assert len(planned.cohort.excluded) == 149
    invalid = argv.copy()
    invalid[invalid.index("normal/qiskitHumanEval/2")] = "hard/qiskitHumanEval/2"
    invalid[4] = str(tmp_path / "invalid.json")
    monkeypatch.setattr(sys, "argv", invalid)
    with pytest.raises(SystemExit):
        main()
    assert not (tmp_path / "invalid.json").exists()


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_new_protected_run_rejects_hand_edited_retry_policy(ledger):
    frozen = setup()
    edited = frozen.protocol.model_copy(update={"retry": RetryPolicy()})
    with pytest.raises(StateError, match="single dispatch"):
        ledger.create_run(edited)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("field", ["suite", "cohort", "source", "task", "oracle", "request"])
def test_resume_rejects_identity_drift(ledger, field):
    frozen = setup()
    run = ledger.create_run(frozen.protocol)
    changed = frozen
    if field == "suite":
        changed = frozen.model_copy(
            update={"protocol": frozen.protocol.model_copy(update={"protected_suite": "hard"})}
        )
    elif field == "cohort":
        changed = frozen.model_copy(
            update={"cohort": frozen.cohort.model_copy(update={"excluded": {}})}
        )
    elif field == "source":
        changed = frozen.model_copy(
            update={
                "protocol": frozen.protocol.model_copy(update={"generation_code_digest": "0" * 64})
            }
        )
    elif field == "task":
        task = frozen.tasks[0]
        changed = frozen.model_copy(update={"tasks": (task.model_copy(update={"cases": ()}),)})
    elif field == "oracle":
        changed = frozen.model_copy(
            update={"protocol": frozen.protocol.model_copy(update={"judge_digest": "0" * 64})}
        )
    elif field == "request":
        changed = frozen.model_copy(
            update={"protocol": frozen.protocol.model_copy(update={"request_digests": {}})}
        )
    with pytest.raises((StateError, ValueError)):
        changed.validate_for_run(Path(CACHE), ledger.protocol(run))


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_post_hoc_exclusion_and_143_label_are_rejected():
    frozen = setup()
    cohort = frozen.cohort
    with pytest.raises(ValueError):
        cohort.model_copy(update={"excluded": {}}).model_validate_json(
            cohort.model_copy(update={"excluded": {}}).model_dump_json()
        )
    with pytest.raises(ValueError):
        cohort.model_copy(update={"population": "offline_143"}).model_validate_json(
            cohort.model_copy(update={"population": "offline_143"}).model_dump_json()
        )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_comparison_rejects_cross_track_or_suite():
    frozen = setup()
    for changed in (
        frozen.protocol.model_copy(update={"track": "qhe-pinned-native-v1"}),
        frozen.protocol.model_copy(update={"protected_suite": "hard"}),
    ):
        with pytest.raises((StateError, ValueError)):
            plan = ComparisonPlan(
                left=frozen.protocol,
                right=changed,
                families={"normal/qiskitHumanEval/20": "qhe/20"},
                seed=1,
                configuration_comparison="fixture",
                analysis_source=source_manifest()["digest"],
            )
            validate_plan(plan)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_cli_plan_and_create_are_offline(tmp_path, monkeypatch, capsys):
    model_path = tmp_path / "model.json"
    setup_path = tmp_path / "setup.json"
    ledger_path = tmp_path / "ledger.sqlite"
    model_path.write_text(MODEL.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "protected-plan",
            str(model_path),
            CACHE,
            str(setup_path),
            "--name",
            "fixture",
            "--label",
            "task20",
            "--suite",
            "normal",
            "--task",
            "normal/qiskitHumanEval/20",
            "--image",
            IMAGE,
        ],
    )
    main()
    plan = json.loads(capsys.readouterr().out)
    assert plan["planned_samples"] == 1
    assert plan["publication_eligible"] is False
    monkeypatch.setattr(
        sys, "argv", ["graybench", "protected-create", str(setup_path), CACHE, str(ledger_path)]
    )
    main()
    run = json.loads(capsys.readouterr().out)
    assert run["suite"] == "normal"
    assert run["publication_eligible"] is False


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_claim_first_protected_ledger_and_interruption(ledger, monkeypatch):
    frozen = setup()
    run = ledger.create_run(frozen.protocol)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        campaign = ProtectedCampaign(
            ledger, run, frozen, Path(CACHE), Transport(MODEL, client=client)
        )
        assert campaign.step()["state"] == "dispatched"
        sample = ledger.samples(run)[0]["id"]
        with pytest.raises(StateError, match="prior.*claim"):
            ledger.judge(sample, frozen.protocol.judge_digest, "pass", {})
        with pytest.raises(StateError, match="judge identity"):
            ledger.claim_judgment(sample, "0" * 64)
        original = campaign.judge.evaluate

        def interrupted(*args):
            raise KeyboardInterrupt()

        monkeypatch.setattr(campaign.judge, "evaluate", interrupted)
        with pytest.raises(KeyboardInterrupt):
            campaign.step()
        assert campaign.step() == {"state": "stopped", "reason": "unresolved_judgment"}
        monkeypatch.setattr(campaign.judge, "evaluate", original)
    assert ledger.summary(run)["pass_at_1"] is None
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_protected_ledger_reference_and_wrong_control(ledger):
    first = setup()
    frozen = build_protected_setup(
        "two answers", MODEL, first.cohort, first.tasks, cache=Path(CACHE), repeats=2
    )
    answers = iter(
        (
            direct_solution(),
            "def ghz_amplitudes(layout):\n"
            "    return [[1.0,0.0]] + [[0.0,0.0] for _ in range(127)]\n",
        )
    )

    def response(request):
        if request.url.path != "/api/chat":
            return handler(request)
        return httpx.Response(
            200,
            json={
                "model": "fixture",
                "done": True,
                "message": {"role": "assistant", "content": next(answers)},
            },
        )

    run = ledger.create_run(frozen.protocol)
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        campaign = ProtectedCampaign(
            ledger, run, frozen, Path(CACHE), Transport(MODEL, client=client)
        )
        states = [campaign.step() for _ in range(5)]
    assert [item["state"] for item in states] == [
        "dispatched",
        "judged",
        "dispatched",
        "judged",
        "judgments_complete",
    ]
    assert [item["outcome"] for item in states if item["state"] == "judged"] == [
        "pass",
        "fail",
    ]
    report = ledger.summary(run)
    assert report["complete"] is True
    assert report["score_status"] == "development_only"
    assert report["population"] == "custom_development"
    assert report["denominator"] == 2
    assert report["pass_at_1"] == 0.5
    assert report["publication_eligible"] is False
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_two_task_campaign_generates_and_judges_each_revised_value(ledger, suite):
    frozen = two_task_setup(suite)
    answers = iter(
        (
            "def bell_amplitudes():\n"
            "    import math\n"
            "    a = 1 / math.sqrt(2)\n"
            "    return [[a,0.0],[0.0,0.0],[0.0,0.0],[a,0.0]]\n",
            direct_solution(),
        )
    )

    def response(request):
        if request.url.path != "/api/chat":
            return handler(request)
        return httpx.Response(
            200,
            json={
                "model": "fixture",
                "done": True,
                "message": {"role": "assistant", "content": next(answers)},
            },
        )

    run = ledger.create_run(frozen.protocol)
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        campaign = ProtectedCampaign(
            ledger, run, frozen, Path(CACHE), Transport(MODEL, client=client)
        )
        states = [campaign.step() for _ in range(5)]
    assert [item["state"] for item in states] == [
        "dispatched",
        "judged",
        "dispatched",
        "judged",
        "judgments_complete",
    ]
    assert [item["outcome"] for item in states if item["state"] == "judged"] == [
        "pass",
        "pass",
    ]
    report = ledger.summary(run)
    assert report["denominator"] == 2
    assert report["pass_at_1"] == 1.0
    assert report["publication_eligible"] is False
    assert ledger.verify()["integrity"] == "verified"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_verifier_rejects_protected_judgment_without_claim(ledger, monkeypatch):
    frozen = setup()
    run = ledger.create_run(frozen.protocol)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        campaign = ProtectedCampaign(
            ledger, run, frozen, Path(CACHE), Transport(MODEL, client=client)
        )
        assert campaign.step()["state"] == "dispatched"
    sample = ledger.samples(run)[0]["id"]
    monkeypatch.setattr(ledger, "_require_native_judge_claim", lambda *_: None)
    ledger.judge(sample, frozen.protocol.judge_digest, "pass", {})
    with pytest.raises(ValueError, match="prior durable claim"):
        ledger.verify()

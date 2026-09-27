import json
import sys

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.cli import main
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import validate_cohort
from graybench.ledger import StateError


def private_task(task):
    return JudgeTask(
        public=task,
        canonical_solution="SECRET_REFERENCE_SENTINEL",
        upstream_test="SECRET_TEST_SENTINEL",
        upstream_difficulty="fixture",
    )


def test_builder_binds_requests_without_including_private_source(model, task):
    private = private_task(task)
    setup = build_setup("fixture", model, (private,), "sha256:" + "0" * 64, repeats=3)
    validate_cohort(setup.protocol, (private,), setup.judge())
    assert setup.protocol.repeats == 3
    assert "SECRET_REFERENCE_SENTINEL" not in setup.model_dump_json()
    assert "SECRET_TEST_SENTINEL" not in setup.model_dump_json()
    with pytest.raises(StateError, match="unique"):
        build_setup("duplicate", model, (private, private), setup.image)


def test_builder_can_freeze_attempt_bound_observation_protocol(model, task):
    setup = build_setup(
        "pre-post",
        model,
        (private_task(task),),
        "sha256:" + "0" * 64,
        protocol_version="3.2",
    )
    assert setup.protocol.schema_version == "3.2"
    assert CampaignSetup.model_validate_json(setup.model_dump_json()).protocol == setup.protocol


def test_extraction_policy_is_frozen_in_judge_and_cohort(model, task):
    private = private_task(task)
    image = "sha256:" + "0" * 64
    original = build_setup("v1", model, (private,), image)
    revised = build_setup(
        "v2",
        model,
        (private,),
        image,
        extraction="unique_entrypoint_fence_v2",
    )
    assert revised.protocol.extraction == "unique_entrypoint_fence_v2"
    assert revised.protocol.judge_digest != original.protocol.judge_digest
    restored = CampaignSetup.model_validate_json(revised.model_dump_json())
    validate_cohort(restored.protocol, (private,), restored.judge())
    with pytest.raises(StateError, match="extraction|judge_digest"):
        validate_cohort(revised.protocol, (private,), original.judge())
    forged = original.protocol.model_copy(update={"extraction": "unique_entrypoint_fence_v2"})
    with pytest.raises(StateError, match="extraction"):
        validate_cohort(forged, (private,), original.judge())


def test_indented_fence_policy_has_a_distinct_frozen_judge(model, task):
    private = private_task(task)
    image = "sha256:" + "0" * 64
    v2 = build_setup("v2", model, (private,), image, extraction="unique_entrypoint_fence_v2")
    v3 = build_setup("v3", model, (private,), image, extraction="unique_entrypoint_fence_v3")
    assert v3.protocol.judge_digest != v2.protocol.judge_digest
    assert v3.protocol.request_digests == v2.protocol.request_digests
    validate_cohort(v3.protocol, (private,), v3.judge())
    with pytest.raises(StateError, match="extraction|judge_digest"):
        validate_cohort(v3.protocol, (private,), v2.judge())


@pytest.mark.parametrize("extraction", ("unique_entrypoint_fence_v2", "unique_entrypoint_fence_v3"))
def test_cli_plan_freezes_explicit_extraction(tmp_path, model, task, monkeypatch, extraction):
    private = private_task(task)
    monkeypatch.setattr(
        "graybench.cli.load_suite", lambda suite, _: (private,) if suite == "hard" else ()
    )
    spec = tmp_path / "model.json"
    spec.write_text(model.model_dump_json())
    output = tmp_path / "setup.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "campaign-plan",
            str(spec),
            str(tmp_path),
            str(output),
            "--image",
            "sha256:" + "0" * 64,
            "--name",
            "extraction-condition",
            "--suite",
            "hard",
            "--extraction",
            extraction,
            "--protocol-version",
            "3.2",
        ],
    )
    main()
    frozen = CampaignSetup.model_validate_json(output.read_bytes()).protocol
    assert frozen.schema_version == "3.2"
    assert frozen.extraction == extraction


def test_cli_plan_freezes_model_observation_timing(tmp_path, model, task, monkeypatch):
    private = private_task(task)
    monkeypatch.setattr(
        "graybench.cli.load_suite", lambda suite, _: (private,) if suite == "hard" else ()
    )
    spec = tmp_path / "model.json"
    spec.write_text(model.model_dump_json())
    output = tmp_path / "setup.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "campaign-plan",
            str(spec),
            str(tmp_path),
            str(output),
            "--image",
            "sha256:" + "0" * 64,
            "--name",
            "timed",
            "--suite",
            "hard",
            "--protocol-version",
            "3.3",
            "--max-pre-observation-age",
            "45",
            "--max-post-observation-delay",
            "240",
        ],
    )
    main()
    frozen = CampaignSetup.model_validate_json(output.read_bytes()).protocol
    assert frozen.model_observation_timing.max_pre_age_seconds == 45
    assert frozen.model_observation_timing.max_post_delay_seconds == 240


def test_cli_plan_is_offline_explicit_and_does_not_overwrite(
    tmp_path, model, task, monkeypatch, capsys
):
    private = private_task(task)
    monkeypatch.setattr(
        "graybench.cli.load_suite", lambda suite, _: (private,) if suite == "hard" else ()
    )
    monkeypatch.setattr(
        "graybench.cli.Transport",
        lambda *_args, **_kwargs: pytest.fail("planning must not contact provider"),
    )
    spec = tmp_path / "model.json"
    spec.write_text(model.model_dump_json())
    output = tmp_path / "setup.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "campaign-plan",
            str(spec),
            str(tmp_path),
            str(output),
            "--image",
            "sha256:" + "0" * 64,
            "--name",
            "offline",
            "--suite",
            "both",
            "--repeats",
            "2",
        ],
    )
    main()
    result = json.loads(capsys.readouterr().out)
    setup = CampaignSetup.model_validate_json(output.read_bytes())
    assert result["planned_samples"] == 2
    assert setup.protocol.task_keys == ("hard/qiskitHumanEval/0",)
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        main()
    assert output.read_bytes() == original

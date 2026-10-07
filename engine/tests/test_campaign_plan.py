import json
import sys

import pytest

from graybench.adapter_provenance import adapter_code_manifest
from graybench.campaign_setup import CampaignSetup, build_setup, execution_context
from graybench.cli import main
from graybench.contracts import ModelSpec, Setting
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import validate_cohort
from graybench.ledger import StateError
from graybench.providers import Ollama


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
    assert setup.protocol.retry.max_attempts == 1
    assert setup.protocol.retry.statuses == ()
    assert setup.protocol.adapter_code_manifest == adapter_code_manifest(Ollama())
    assert "SECRET_REFERENCE_SENTINEL" not in setup.model_dump_json()
    assert "SECRET_TEST_SENTINEL" not in setup.model_dump_json()
    with pytest.raises(StateError, match="unique"):
        build_setup("duplicate", model, (private, private), setup.image)


def test_campaign_creation_rejects_adapter_manifest_drift(model, task):
    setup = build_setup("fixture", model, (private_task(task),), "sha256:" + "0" * 64)
    changed = {**setup.protocol.adapter_code_manifest, "engine_source_digest": "0" * 64}
    forged = setup.model_copy(
        update={"protocol": setup.protocol.model_copy(update={"adapter_code_manifest": changed})}
    )
    with pytest.raises(StateError, match="(?i)adapter.*code"):
        execution_context(forged)


def test_new_credentialed_campaign_requires_public_account_scope(task):
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
    )
    private = private_task(task)
    with pytest.raises(ValueError, match="credential_scope_id"):
        build_setup("missing-scope", model, (private,), "sha256:" + "0" * 64)
    declared = model.model_copy(update={"credential_scope_id": "openai/project/benchmark"})
    setup = build_setup("declared-scope", declared, (private,), "sha256:" + "0" * 64)
    assert setup.protocol.model.credential_scope_id == "openai/project/benchmark"


def test_copied_model_cannot_put_loaded_key_into_campaign_artifact(monkeypatch, task):
    monkeypatch.setenv("TEST_TOKEN", "unit-secret-456")
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
    )
    bypassed = model.model_copy(update={"credential_scope_id": "openai/project/unit-secret-456"})
    with pytest.raises(ValueError, match="credential_scope_id"):
        build_setup(
            "copied-scope",
            bypassed,
            (private_task(task),),
            "sha256:" + "0" * 64,
        )


def test_campaign_cannot_freeze_setting_containing_key_loaded_later(monkeypatch, task):
    secret = "unit-secret-plan-789"
    monkeypatch.delenv("TEST_TOKEN", raising=False)
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
        credential_scope_id="openai/project/benchmark",
        settings=(Setting(name="stop", value=secret, support="documented", evidence="docs"),),
    )
    monkeypatch.setenv("TEST_TOKEN", secret)
    with pytest.raises(ValueError, match="credential"):
        build_setup("secret-setting", model, (private_task(task),), "sha256:" + "0" * 64)


def test_campaign_and_ledger_cannot_store_key_in_system_prompt(monkeypatch, task, ledger):
    secret = "unit-secret-prompt-789"
    monkeypatch.setenv("TEST_TOKEN", secret)
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
        credential_scope_id="openai/project/benchmark",
    )
    private = private_task(task)
    image = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="credential"):
        build_setup("secret-prompt", model, (private,), image, system_prompt=secret)
    setup = build_setup("safe-prompt", model, (private,), image, system_prompt="public")
    forged = setup.protocol.model_copy(update={"system_prompt": secret})
    with pytest.raises(ValueError, match="credential"):
        ledger.create_run(forged)
    assert ledger.verify()["events"] == 0


def test_campaign_and_ledger_reject_key_in_other_public_artifacts(monkeypatch, task, ledger):
    secret = "unit-secret-artifact-789"
    monkeypatch.setenv("TEST_TOKEN", secret)
    model = ModelSpec(
        adapter="openai-chat",
        model="test",
        base_url="https://example.test",
        credential_env="TEST_TOKEN",
        credential_scope_id="openai/project/benchmark",
    )
    private = private_task(task)
    image = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="credential"):
        build_setup(secret, model, (private,), image)
    setup = build_setup("safe", model, (private,), image)
    with pytest.raises(ValueError, match="credential"):
        ledger.create_run(setup.protocol, {"operator_note": secret})
    assert ledger.verify()["events"] == 0


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

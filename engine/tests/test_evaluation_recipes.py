import json
import os
import sys

import httpx
import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.cli import main
from graybench.comparison import make_plan
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import UpstreamCampaign, validate_cohort
from graybench.ledger import Ledger, StateError
from graybench.oracle_review import PAULI_CONTRACT
from graybench.providers import Ollama
from graybench.transport import Transport

RECIPE = "qhe141-pauli-group-anticommutator-v1"
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "0" * 64)
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")


def pauli_task(task):
    return JudgeTask(
        public=task.model_copy(
            update={
                "task_id": "qiskitHumanEval/141",
                "family_id": "qhe/141",
                "entry_point": "anticommutators",
                "prompt": "Return ten Pauli operators whose anticommutator is scalar identity.",
            }
        ),
        canonical_solution="PRIVATE_REFERENCE_SENTINEL",
        upstream_test="PRIVATE_TEST_SENTINEL",
        upstream_difficulty="fixture",
    )


def test_recipe_plan_freezes_revised_public_request_and_reconstructs(model, task, monkeypatch):
    original = pauli_task(task)
    setup = build_setup("revision", model, (original,), IMAGE, evaluation_recipe=RECIPE)
    assert setup.protocol.track == "strengthened"
    key = "hard/qiskitHumanEval/141"
    assert (
        setup.protocol.request_digests[key] != Ollama().prepare(model, original.public, None).digest
    )
    monkeypatch.setattr(
        "graybench.campaign_setup.load_suite",
        lambda suite, _: (original,) if suite == "hard" else (),
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    (revised,) = restored.tasks(None)
    assert PAULI_CONTRACT in revised.public.prompt
    validate_cohort(restored.protocol, (revised,), restored.judge())
    with pytest.raises((StateError, ValueError)):
        validate_cohort(restored.protocol, (original,), restored.judge())
    assert "PRIVATE_REFERENCE_SENTINEL" not in setup.model_dump_json()
    assert "PRIVATE_TEST_SENTINEL" not in setup.model_dump_json()


@pytest.mark.parametrize(
    "recipe",
    ["qhe0-size-domain-v1", "task82-file-semantic-v1", "qhe113-barrier-metrics-v1", "unknown"],
)
def test_recipe_rejects_wrong_family_or_unknown_name(model, task, recipe):
    with pytest.raises(ValueError):
        build_setup("wrong", model, (pauli_task(task),), IMAGE, evaluation_recipe=recipe)


@pytest.mark.parametrize(
    "recipe,family,entry",
    [
        ("qhe0-size-domain-v1", "qhe/0", "create_quantum_circuit"),
        ("task82-file-semantic-v1", "qhe/82", "create_binary_serialization"),
    ],
)
def test_other_recipes_bind_limits_and_keep_public_prompt(model, task, recipe, family, entry):
    original = pauli_task(task)
    original = original.model_copy(
        update={
            "public": original.public.model_copy(
                update={
                    "family_id": family,
                    "entry_point": entry,
                    "task_id": family.replace("qhe", "qiskitHumanEval"),
                }
            )
        }
    )
    setup = build_setup("other", model, (original,), IMAGE, evaluation_recipe=recipe)
    validate_cohort(setup.protocol, (original,), setup.judge())
    assert setup.protocol.track == "strengthened"
    changed = setup.model_copy(update={"output_limit": 2048})
    with pytest.raises(StateError, match="judge_digest"):
        validate_cohort(setup.protocol, (original,), changed.judge())
    if family == "qhe/82":
        changed = setup.model_copy(update={"parser_timeout": 31.0})
        with pytest.raises(StateError, match="judge_digest"):
            validate_cohort(setup.protocol, (original,), changed.judge())


def test_cli_freezes_explicit_recipe_without_network(model, task, tmp_path, monkeypatch, capsys):
    original = pauli_task(task)
    monkeypatch.setattr(
        "graybench.cli.load_suite", lambda suite, _: (original,) if suite == "hard" else ()
    )
    monkeypatch.setattr("graybench.cli.Transport", lambda *a, **k: pytest.fail("Offline plan"))
    spec, output = tmp_path / "model.json", tmp_path / "setup.json"
    spec.write_text(model.model_dump_json())
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
            IMAGE,
            "--name",
            "explicit",
            "--suite",
            "hard",
            "--evaluation-recipe",
            RECIPE,
        ],
    )
    main()
    saved = CampaignSetup.model_validate_json(output.read_bytes())
    assert saved.evaluation_recipe == RECIPE
    assert json.loads(capsys.readouterr().out)["evaluation_recipe"] == RECIPE


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
def test_revised_campaign_binds_real_protected_judgment_to_public_request(
    model, task, ledger, monkeypatch
):
    original = pauli_task(task)
    setup = build_setup("revision", model, (original,), IMAGE, evaluation_recipe=RECIPE)
    monkeypatch.setattr(
        "graybench.campaign_setup.load_suite",
        lambda suite, _: (original,) if suite == "hard" else (),
    )
    tasks = setup.tasks(None)
    run = ledger.create_run(setup.protocol, {"setup": setup.model_dump(mode="json")})
    requests = []

    def handler(request):
        requests.append(request.content.decode())
        return httpx.Response(
            200,
            json={
                "model": model.model,
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": "def anticommutators(pauli):\n    return [pauli]*10",
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        transport = Transport(model, client=client)
        campaign = UpstreamCampaign(ledger, run, tasks, setup.judge(DOCKER), transport)
        assert campaign.step()["state"] == "dispatched"
        assert campaign.step()["outcome"] == "pass"
    assert len(requests) == 1
    assert PAULI_CONTRACT in requests[0]
    assert "PRIVATE_" not in requests[0]
    summary = ledger.summary(run)
    assert summary["evaluation_recipe"] == RECIPE
    assert summary["track"] == "strengthened"
    assert summary["publication_eligible"] is False


def test_cli_comparison_reconstructs_revision_from_both_run_contexts(
    model, task, tmp_path, monkeypatch, capsys
):
    original = pauli_task(task)

    def selected(suite, _):
        return (original,) if suite == "hard" else ()

    monkeypatch.setattr("graybench.campaign_setup.load_suite", selected)
    monkeypatch.setattr("graybench.cli.load_suite", selected)
    setups = [
        build_setup(name, model, (original,), IMAGE, evaluation_recipe=RECIPE)
        for name in ("left", "right")
    ]
    plan = make_plan(
        setups[0].protocol,
        setups[1].protocol,
        setups[0].tasks(None),
        seed=1,
        resamples=1000,
        configuration_comparison="Synthetic integration",
    )
    plan_path, output = tmp_path / "plan.json", tmp_path / "comparison.json"
    plan_path.write_text(plan.model_dump_json())
    paths = [tmp_path / "left.sqlite", tmp_path / "right.sqlite"]
    runs = []
    for setup, path in zip(setups, paths, strict=True):
        book = Ledger(path)
        try:
            runs.append(book.create_run(setup.protocol, {"setup": setup.model_dump(mode="json")}))
        finally:
            book.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "compare",
            str(plan_path),
            str(paths[0]),
            runs[0],
            str(paths[1]),
            runs[1],
            str(tmp_path),
            str(output),
        ],
    )
    main()
    report = json.loads(output.read_text())
    assert report["publication_eligible"] is False
    assert [run["evaluation_recipe"] for run in report["runs"]] == [RECIPE, RECIPE]
    assert report["status"] == "unscored"
    capsys.readouterr()

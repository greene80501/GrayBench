import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from test_native_cohort import IMAGE, selected
from test_native_cohort import cache as _synthetic_cache
from test_capability_probe import accepted_probe, matching_profile, spec

from graybench.adapter_provenance import adapter_code_manifest
from graybench.campaign_setup import build_setup
from graybench.cli import main
from graybench.comparison import ComparisonPlan, validate_plan
from graybench.contracts import (
    CapabilityProfile,
    ModelObservationTiming,
    ModelSpec,
    Protocol,
    RetryPolicy,
)
from graybench.ledger import StateError
from graybench.native_campaign import NativeCampaign, NativeCampaignSetup, build_native_setup
from graybench.native_cohort import freeze_native_cohort
from graybench.provenance import source_manifest
from graybench.providers import Ollama
from graybench.transport import Transport

MODEL = ModelSpec(adapter="ollama", model="fixture", base_url="http://localhost:11434")


@pytest.fixture
def native_cache(tmp_path, monkeypatch):
    return _synthetic_cache.__wrapped__(tmp_path, monkeypatch)


def test_historical_protocol_digest_and_ledger_remain_readable(ledger):
    historical = Protocol(
        schema_version="3.3",
        name="historical",
        track="upstream",
        dataset_digest="1" * 64,
        task_keys=("normal/qiskitHumanEval/0",),
        request_digests={"normal/qiskitHumanEval/0": "2" * 64},
        model=MODEL,
        model_observation_timing=ModelObservationTiming(),
        generation_code_digest="3" * 64,
        runtime_digest="4" * 64,
        judge_digest="5" * 64,
        analysis_digest="6" * 64,
    )
    assert historical.digest == "ba59136d0f7d9845d61184f2c4ae6b1c128b323e2c087376cd05604d06c9aa45"
    assert "native_cohort_digest" not in historical.model_dump(mode="json")
    run = ledger.create_run(historical)
    assert ledger.protocol(run).digest == historical.digest
    assert ledger.verify()["integrity"] == "verified"


def native_setup(cache, suite="normal", exception_policy="conservative_unattributed_v1"):
    tasks, excluded = selected(cache, suite, "custom_development")
    cohort = freeze_native_cohort(
        tasks,
        cache=cache,
        suite=suite,
        population="custom_development",
        image=IMAGE,
        extraction="raw_or_single_python_fence_v1",
        exception_policy=exception_policy,
        label="fixture two tasks",
        excluded=excluded,
    )
    return build_native_setup("fixture", MODEL, cohort, tasks, cache=cache)


def test_native_plan_rejects_missing_capability_probe_artifact(native_cache):
    tasks, excluded = selected(native_cache, "normal", "custom_development")
    cohort = freeze_native_cohort(
        tasks,
        cache=native_cache,
        suite="normal",
        population="custom_development",
        image=IMAGE,
        extraction="raw_or_single_python_fence_v1",
        label="probe requirement",
        excluded=excluded,
    )
    profile = CapabilityProfile(
        adapter="ollama",
        model="fixture",
        base_url="http://localhost:11434",
        generation_path="/api/chat",
        checked_on="2026-09-28",
        documentation=("https://docs.ollama.com/api/chat",),
        probe_digests=("a" * 64,),
    )
    with pytest.raises(ValueError, match="probe"):
        build_native_setup(
            "missing-probe",
            MODEL.model_copy(update={"capability_profile": profile}),
            cohort,
            tasks,
            cache=native_cache,
        )


def test_native_plan_freezes_verified_capability_probe(native_cache):
    baseline = native_setup(native_cache)
    record = accepted_probe()
    qualified = build_native_setup(
        "with-probe",
        spec(profile=matching_profile(record)),
        baseline.cohort,
        baseline.tasks(native_cache),
        cache=native_cache,
        capability_probes=(record,),
    )
    restored = NativeCampaignSetup.model_validate_json(qualified.model_dump_json())
    assert restored.capability_probes[0].digest == record.digest
    assert restored.validate_for_run(native_cache, restored.protocol)


def test_native_resume_rejects_adapter_code_drift(native_cache, monkeypatch):
    result = native_setup(native_cache)
    changed = {**result.protocol.adapter_code_manifest, "engine_source_digest": "0" * 64}
    monkeypatch.setattr("graybench.native_campaign.adapter_code_manifest", lambda provider: changed)
    with pytest.raises(StateError, match="(?i)adapter code"):
        result.validate_for_run(native_cache, result.protocol)


def test_explicit_exception_policy_is_visible_in_protocol_and_report(native_cache, ledger):
    conservative = native_setup(native_cache)
    scored = native_setup(native_cache, exception_policy="test_exception_is_failure_v1")
    assert conservative.protocol.native_exception_policy is None
    assert "native_exception_policy" not in conservative.protocol.model_dump(mode="json")
    assert scored.protocol.native_exception_policy == "test_exception_is_failure_v1"
    assert scored.protocol.digest != conservative.protocol.digest
    run = ledger.create_run(scored.protocol)
    assert ledger.summary(run)["native_exception_policy"] == "test_exception_is_failure_v1"
    edited = scored.protocol.model_copy(update={"native_exception_policy": None})
    with pytest.raises(StateError, match="differs"):
        scored.validate_for_run(native_cache, edited)


def test_native_setup_is_single_suite_and_development_only(native_cache, ledger):
    cache = native_cache
    setup = native_setup(cache)
    assert setup.protocol.adapter_code_manifest == adapter_code_manifest(Ollama())
    assert isinstance(setup, NativeCampaignSetup)
    hard = native_setup(cache, "hard")
    assert setup.protocol.track == "qhe-pinned-native-v1"
    assert setup.protocol.native_cohort_digest == setup.cohort.digest
    assert setup.protocol.native_suite == "normal"
    assert setup.protocol.native_population == "custom_development"
    assert setup.protocol.retry.max_attempts == 1
    assert setup.protocol.retry.statuses == ()
    assert setup.digest != hard.digest
    assert setup.tasks(cache)[0].public.suite == "normal"
    run = ledger.create_run(setup.protocol)
    report = ledger.summary(run)
    assert report["track"] == "qhe-pinned-native-v1"
    assert report["suite"] == "normal"
    assert report["population"] == "custom_development"
    assert report["native_cohort_digest"] == setup.cohort.digest
    assert report["planned_samples"] == 2
    assert report["pass_at_1"] is None
    assert report["publication_eligible"] is False


def test_new_native_run_rejects_hand_edited_retry_policy(native_cache, ledger):
    setup = native_setup(native_cache)
    edited = setup.protocol.model_copy(update={"retry": RetryPolicy()})
    with pytest.raises(StateError, match="single dispatch"):
        ledger.create_run(edited)


@pytest.mark.parametrize(
    "field", ["suite", "population", "cohort", "image", "extraction", "task", "judge", "source"]
)
def test_native_resume_rejects_changed_identity(native_cache, ledger, field):
    cache = native_cache
    setup = native_setup(cache)
    run = ledger.create_run(setup.protocol)
    if field == "suite":
        changed = setup.protocol.model_copy(update={"native_suite": "hard"})
    elif field == "population":
        changed = setup.protocol.model_copy(update={"native_population": "offline_143"})
    elif field == "cohort":
        changed = setup.protocol.model_copy(update={"native_cohort_digest": "0" * 64})
    elif field == "image":
        changed = setup.model_copy(
            update={"cohort": setup.cohort.model_copy(update={"image": "sha256:" + "b" * 64})}
        )
    elif field == "extraction":
        changed = setup.model_copy(
            update={
                "cohort": setup.cohort.model_copy(
                    update={"extraction": "unique_entrypoint_fence_v3"}
                )
            }
        )
    elif field == "task":
        altered = setup.tasks(cache)[0].model_copy(
            update={"upstream_test": "def check(candidate): pass"}
        )
        tasks = (altered,) + setup.tasks(cache)[1:]
        changed = setup
    elif field == "judge":
        changed = setup.protocol.model_copy(update={"judge_digest": "0" * 64})
    else:
        changed = setup.protocol.model_copy(update={"generation_code_digest": "0" * 64})
    if isinstance(changed, Protocol):
        changed = setup.model_copy(update={"protocol": changed})
    with pytest.raises((StateError, ValueError)):
        changed.validate_for_run(
            cache, ledger.protocol(run), tasks=tasks if field == "task" else None
        )


def test_native_protocol_cannot_mix_suites_or_omit_binding(native_cache):
    cache = native_cache
    setup = native_setup(cache)
    data = setup.protocol.model_dump(mode="json")
    data["task_keys"].append("hard/qiskitHumanEval/0")
    data["request_digests"]["hard/qiskitHumanEval/0"] = "0" * 64
    with pytest.raises(ValueError):
        Protocol.model_validate(data)
    data = setup.protocol.model_dump(mode="json")
    del data["native_cohort_digest"]
    with pytest.raises(ValueError):
        Protocol.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("track", "upstream"),
        ("native_suite", "hard"),
        ("extraction", "exact_prompt_suffix_v1"),
        ("native_exception_policy", "test_exception_is_failure_v1"),
    ],
)
def test_comparison_rejects_mixed_native_tracks_or_suites(native_cache, field, value):
    setup = native_setup(native_cache)
    right = setup.protocol.model_copy(update={field: value})
    with pytest.raises((StateError, ValueError)):
        plan = ComparisonPlan(
            left=setup.protocol,
            right=right,
            families={key: key for key in setup.protocol.task_keys},
            seed=1,
            configuration_comparison="fixture",
            analysis_source=source_manifest()["digest"],
        )
        validate_plan(plan)


def test_campaign_checks_binding_before_dispatch(native_cache, ledger):
    cache = native_cache
    setup = native_setup(cache)
    run = ledger.create_run(setup.protocol)

    class NoTransport:
        spec = MODEL

        def discover(self, *_, **__):
            return []

        def generate(self, *_):
            pytest.fail("network must not run")

    campaign = NativeCampaign(ledger, run, setup, cache, NoTransport())
    assert campaign.step()["state"] == "stopped"
    setup.cohort.task_digests[setup.cohort.task_keys[0]] = "0" * 64
    with pytest.raises((StateError, ValueError)):
        campaign.step()


def test_native_cli_plan_create_and_summary(native_cache, tmp_path, monkeypatch, capsys):
    model_path = tmp_path / "model.json"
    setup_path = tmp_path / "setup.json"
    ledger_path = tmp_path / "ledger.sqlite"
    model_path.write_text(MODEL.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "native-plan",
            str(model_path),
            str(native_cache),
            str(setup_path),
            "--name",
            "fixture",
            "--label",
            "one task",
            "--suite",
            "normal",
            "--population",
            "custom_development",
            "--task",
            "normal/qiskitHumanEval/0",
            "--image",
            IMAGE,
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["planned_samples"] == 1
    monkeypatch.setattr(
        sys,
        "argv",
        ["graybench", "native-create", str(setup_path), str(native_cache), str(ledger_path)],
    )
    main()
    run = json.loads(capsys.readouterr().out)
    assert run["suite"] == "normal"
    monkeypatch.setattr(sys, "argv", ["graybench", "summary", str(ledger_path), run["run_id"]])
    main()
    report = json.loads(capsys.readouterr().out)
    assert report["denominator"] == 1
    assert report["publication_eligible"] is False


def test_native_plan_freezes_exact_suffix_condition_and_rejects_hard_suite(
    native_cache, tmp_path, monkeypatch, capsys, ledger
):
    model_path = tmp_path / "model.json"
    model_path.write_text(MODEL.model_dump_json(), encoding="utf-8")
    normal_path = tmp_path / "normal.json"
    argv = [
        "graybench",
        "native-plan",
        str(model_path),
        str(native_cache),
        str(normal_path),
        "--name",
        "literal",
        "--label",
        "literal condition",
        "--suite",
        "normal",
        "--population",
        "custom_development",
        "--task",
        "normal/qiskitHumanEval/0",
        "--image",
        IMAGE,
        "--extraction",
        "exact_prompt_suffix_v1",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    main()
    plan = json.loads(capsys.readouterr().out)
    saved = NativeCampaignSetup.model_validate_json(normal_path.read_bytes())
    assert saved.protocol.extraction == "exact_prompt_suffix_v1"
    assert saved.cohort.extraction == "exact_prompt_suffix_v1"
    assert saved.protocol.digest != native_setup(native_cache).protocol.digest
    assert plan["extraction_policy"] == "exact_prompt_suffix_v1"
    run = ledger.create_run(saved.protocol)
    assert ledger.summary(run)["extraction_policy"] == "exact_prompt_suffix_v1"
    invalid = argv.copy()
    invalid[4] = str(tmp_path / "hard.json")
    invalid[invalid.index("normal") + 0] = "hard"
    invalid[invalid.index("normal/qiskitHumanEval/0")] = "hard/qiskitHumanEval/0"
    monkeypatch.setattr(sys, "argv", invalid)
    with pytest.raises(ValueError, match="normal"):
        main()
    assert not (tmp_path / "hard.json").exists()


def test_native_plan_exposes_explicit_test_exception_policy(
    native_cache, tmp_path, monkeypatch, capsys
):
    model_path = tmp_path / "model.json"
    model_path.write_text(MODEL.model_dump_json(), encoding="utf-8")
    output = tmp_path / "native.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "native-plan",
            str(model_path),
            str(native_cache),
            str(output),
            "--name",
            "policy fixture",
            "--label",
            "policy fixture",
            "--suite",
            "hard",
            "--population",
            "custom_development",
            "--task",
            "hard/qiskitHumanEval/0",
            "--image",
            IMAGE,
            "--exception-policy",
            "test_exception_is_failure_v1",
        ],
    )
    main()
    printed = json.loads(capsys.readouterr().out)
    saved = NativeCampaignSetup.model_validate_json(output.read_bytes())
    assert printed["exception_policy"] == "test_exception_is_failure_v1"
    assert saved.cohort.exception_policy == "test_exception_is_failure_v1"
    assert saved.protocol.native_exception_policy == "test_exception_is_failure_v1"


@pytest.mark.parametrize("suite", ["hard", "both"])
def test_shared_campaign_rejects_suffix_policy_when_hard_task_is_scheduled(native_cache, suite):
    tasks = tuple(
        task
        for source_suite in (("hard",) if suite == "hard" else ("normal", "hard"))
        for task in selected(native_cache, source_suite, "custom_development")[0][:1]
    )
    with pytest.raises((StateError, ValueError), match="normal function-completion"):
        build_setup(
            "invalid literal campaign",
            MODEL,
            tasks,
            IMAGE,
            extraction="exact_prompt_suffix_v1",
        )


def test_interrupted_native_judgment_is_not_rerolled(native_cache, ledger, monkeypatch):
    setup = native_setup(native_cache)

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
                "message": {"role": "assistant", "content": "\n    return 0\n"},
            },
        )

    run = ledger.create_run(setup.protocol)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        campaign = NativeCampaign(ledger, run, setup, native_cache, Transport(MODEL, client=client))
        assert campaign.step()["state"] == "dispatched"
        sample = ledger.samples(run)[0]["id"]
        with pytest.raises(StateError, match="prior.*claim"):
            ledger.judge(sample, setup.protocol.judge_digest, "pass", {})
        with pytest.raises(StateError, match="native judge identity"):
            ledger.claim_judgment(sample, "0" * 64)
        calls = []

        def interrupted(*args):
            calls.append(args)
            raise KeyboardInterrupt()

        monkeypatch.setattr(campaign.inner.judgments.judge, "evaluate", interrupted)
        with pytest.raises(KeyboardInterrupt):
            campaign.step()
        assert campaign.step() == {"state": "stopped", "reason": "unresolved_judgment"}
    assert len(calls) == 1
    assert ledger.summary(run)["pass_at_1"] is None


def test_native_verifier_rejects_unclaimed_judgment(native_cache, ledger, monkeypatch):
    setup = native_setup(native_cache)

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
                "message": {"role": "assistant", "content": "\n    return 0\n"},
            },
        )

    run = ledger.create_run(setup.protocol)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        campaign = NativeCampaign(ledger, run, setup, native_cache, Transport(MODEL, client=client))
        assert campaign.step()["state"] == "dispatched"
    sample = ledger.samples(run)[0]["id"]
    monkeypatch.setattr(ledger, "_require_native_judge_claim", lambda *_: None)
    ledger.judge(sample, setup.protocol.judge_digest, "pass", {})
    with pytest.raises(ValueError, match="prior durable claim"):
        ledger.verify()


@pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_IMAGE") or not os.environ.get("GRAYBENCH_TEST_CACHE"),
    reason="Requires the pinned native image and cached parquet",
)
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_native_ledger_reference_and_wrong_control(suite, ledger):
    from graybench.datasets import load_suite

    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    task = load_suite(suite, cache)[0]
    excluded = {
        f"{suite}/qiskitHumanEval/{number}": "out_of_scope_development" for number in range(1, 151)
    }
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite=suite,
        population="custom_development",
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        extraction="raw_or_single_python_fence_v1",
        label="task zero ledger replay",
        excluded=excluded,
    )
    setup = build_native_setup("ledger replay", MODEL, cohort, (task,), cache=cache, repeats=2)
    wrong = (
        "\n    return None\n"
        if suite == "normal"
        else "def create_quantum_circuit(n_qubits):\n    return None\n"
    )
    answers = iter((task.canonical_solution, wrong))

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
                "message": {"role": "assistant", "content": next(answers)},
            },
        )

    run = ledger.create_run(setup.protocol)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        campaign = NativeCampaign(ledger, run, setup, cache, Transport(MODEL, client=client))
        states = [campaign.step() for _ in range(5)]
    assert [state["state"] for state in states] == [
        "dispatched",
        "judged",
        "dispatched",
        "judged",
        "judgments_complete",
    ]
    assert [state["outcome"] for state in states if state["state"] == "judged"] == [
        "pass",
        "fail",
    ]
    report = ledger.summary(run)
    assert report["complete"] is True
    assert report["suite"] == suite
    assert report["denominator"] == 2
    assert report["pass_at_1"] == 0.5
    assert report["publication_eligible"] is False
    assert ledger.verify()["integrity"] == "verified"

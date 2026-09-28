import os
from pathlib import Path

import pytest

from graybench.comparison import compare_runs, family_bootstrap, make_plan, validate_plan
from graybench.contracts import Generation
from graybench.datasets import JudgeTask
from graybench.identity import identity
from graybench.ledger import Ledger, StateError
from graybench.providers import Ollama

PINNED_CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")


def test_paired_bootstrap_preserves_unequal_family_task_weights_and_sign():
    rows = [
        {"family": "a", "samples": 2, "left_passes": 2, "right_passes": 0},
        {"family": "b", "samples": 1, "left_passes": 0, "right_passes": 1},
    ]
    result = family_bootstrap(rows, seed=23, resamples=10000, confidence=0.95)
    assert result["left_minus_right"] == pytest.approx(1 / 3)
    # The exact two-family resampling distribution has support {-1, 1/3, 1}.
    assert result["interval"] == [-1, 1]
    assert family_bootstrap(rows[::-1], seed=23, resamples=10000, confidence=0.95) == result
    reverse = [
        {**r, "left_passes": r["right_passes"], "right_passes": r["left_passes"]} for r in rows
    ]
    swapped = family_bootstrap(reverse, seed=23, resamples=10000, confidence=0.95)
    assert swapped["left_minus_right"] == pytest.approx(-result["left_minus_right"])
    assert swapped["interval"] == [-result["interval"][1], -result["interval"][0]]


@pytest.mark.parametrize(
    "count,reason", [(1, "fewer_than_two_families"), (3, "no_empirical_between_family_variation")]
)
def test_degenerate_bootstrap_does_not_claim_zero_uncertainty(count, reason):
    rows = [
        {"family": str(i), "samples": 2, "left_passes": 2, "right_passes": 0} for i in range(count)
    ]
    result = family_bootstrap(rows, seed=0, resamples=1000, confidence=0.95)
    assert result["left_minus_right"] == 1
    assert result["interval"] is None
    assert result["interval_unavailable_reason"] == reason


def test_historical_comparison_plan_identity_remains_readable():
    import json

    from graybench.comparison import ComparisonPlan

    fixture = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/evaluation-recipe-demo.json"
    )
    record = json.loads(fixture.read_text(encoding="utf-8"))["comparisons"][0]
    restored = ComparisonPlan.model_validate_json(json.dumps(record["plan"]))
    assert identity(record["plan"]) == record["report"]["plan_digest"]
    assert restored.left.model.discovery_policy == "required"
    assert restored.right.model.discovery_policy == "required"


def setup(protocol, task):
    tasks = tuple(
        JudgeTask(
            public=task.model_copy(
                update={"task_id": f"qiskitHumanEval/{i}", "family_id": f"family/{i // 2}"}
            ),
            canonical_solution="return x+1",
            upstream_test="def check(candidate):\n    assert candidate(1)==2",
            upstream_difficulty="fixture",
        )
        for i in range(3)
    )
    keys = {f"{t.public.suite}/{t.public.task_id}": t for t in tasks}
    models = [protocol.model, protocol.model.model_copy(update={"model": "other-model"})]
    protocols = [
        protocol.model_copy(
            update={
                "model": model,
                "task_keys": tuple(keys),
                "dataset_digest": identity({key: t.digest for key, t in keys.items()}),
                "request_digests": {
                    key: Ollama().prepare(model, t.public, None).digest for key, t in keys.items()
                },
            }
        )
        for model in models
    ]
    plan = make_plan(
        *protocols,
        tasks,
        seed=123,
        resamples=1000,
        configuration_comparison="Synthetic adapter fixtures; not real model evidence",
    )
    return plan, tasks


def fill(ledger, protocol, tasks, outcomes):
    run = ledger.create_run(protocol)
    keyed = {f"{t.public.suite}/{t.public.task_id}": t for t in tasks}
    for sample, outcome in zip(ledger.samples(run), outcomes, strict=True):
        attempt = ledger.begin_attempt(
            sample["id"], Ollama().prepare(protocol.model, keyed[sample["task_key"]].public, None)
        )
        ledger.finish_attempt(
            attempt,
            "returned",
            {},
            200,
            Generation(
                text="fixture",
                returned_model=protocol.model.model,
                response_id=None,
                finish_reason="stop",
                usage={},
            ),
        )
        ledger.judge(sample["id"], protocol.judge_digest, outcome, {})
    return run


def test_comparison_uses_verified_cohorts_and_retains_families(tmp_path, protocol, task):
    plan, tasks = setup(protocol, task)
    left, right = Ledger(tmp_path / "left.sqlite"), Ledger(tmp_path / "right.sqlite")
    try:
        a = fill(left, plan.left, tasks, ["pass", "pass", "fail"])
        b = fill(right, plan.right, tasks, ["fail", "fail", "pass"])
        report = compare_runs(plan, left, a, right, b, tasks=tasks)
        assert report["status"] == "development_only"
        assert report["comparison"]["family_count"] == 2
        assert report["comparison"]["left_minus_right"] == pytest.approx(1 / 3)
        assert len(report["families"][0]["tasks"]) == 2
        assert report["publication_eligible"] is False
        changed = plan.model_copy(update={"families": {key: key for key in plan.families}})
        with pytest.raises(StateError, match="family mapping"):
            compare_runs(changed, left, a, right, b, tasks=tasks)
    finally:
        left.close()
        right.close()


def test_unsupported_sample_blocks_the_whole_comparison(tmp_path, protocol, task):
    plan, tasks = setup(protocol, task)
    left, right = Ledger(tmp_path / "left.sqlite"), Ledger(tmp_path / "right.sqlite")
    try:
        a = fill(left, plan.left, tasks, ["pass", "unsupported", "fail"])
        b = fill(right, plan.right, tasks, ["fail", "fail", "pass"])
        report = compare_runs(plan, left, a, right, b, tasks=tasks)
        assert report["status"] == "unscored"
        assert report["comparison"] is None
    finally:
        left.close()
        right.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("runtime_digest", "f" * 64),
        ("system_prompt", "extra help"),
        ("repeats", 2),
        ("schema_version", "3.2"),
    ],
)
def test_incompatible_protocols_cannot_be_compared(protocol, task, field, value):
    plan, _ = setup(protocol, task)
    changed = plan.model_copy(update={"right": plan.right.model_copy(update={field: value})})
    with pytest.raises(StateError, match=field):
        validate_plan(changed)


def test_native_plan_binds_single_suite_and_exception_policy(tmp_path, monkeypatch):
    from test_native_campaign import native_setup
    from test_native_cohort import cache as synthetic_cache

    cache = synthetic_cache.__wrapped__(tmp_path, monkeypatch)
    left = native_setup(cache)
    right = native_setup(cache)
    plan = make_plan(
        left.protocol,
        right.protocol,
        left.tasks(cache),
        seed=5,
        resamples=1000,
        configuration_comparison="Same synthetic model and condition",
    )
    assert plan.left.track == "qhe-pinned-native-v1"
    assert set(plan.families) == set(left.protocol.task_keys)
    changed = plan.model_copy(
        update={
            "right": plan.right.model_copy(
                update={"native_exception_policy": "test_exception_is_failure_v1"}
            )
        }
    )
    with pytest.raises(StateError, match="native_exception_policy"):
        validate_plan(changed)


@pytest.mark.skipif(not PINNED_CACHE, reason="Pinned source cache required")
def test_protected_plan_binds_revised_and_source_task_digests():
    from test_protected_campaign import two_task_setup

    from graybench.protected_campaign import build_protected_setup

    left = two_task_setup()
    right = build_protected_setup(
        "right",
        left.protocol.model.model_copy(update={"model": "other-model"}),
        left.cohort,
        left.tasks,
        cache=Path(PINNED_CACHE),
    )
    plan = make_plan(
        left.protocol,
        right.protocol,
        left.tasks,
        seed=5,
        resamples=1000,
        configuration_comparison="Different synthetic model names",
    )
    assert plan.left.track == "graybench-protected-semantic-v1"
    assert set(plan.families) == set(left.cohort.task_keys)
    assert plan.digest == type(plan).model_validate_json(plan.model_dump_json()).digest
    forged_contract = left.tasks[0].contract.model_copy(update={"source_task_digest": "f" * 64})
    forged = left.tasks[0].model_copy(update={"contract": forged_contract})
    with pytest.raises(StateError, match="dataset identity"):
        make_plan(
            left.protocol,
            right.protocol,
            (forged, *left.tasks[1:]),
            seed=5,
            resamples=1000,
            configuration_comparison="Forged ancestry must fail",
        )
    mixed = plan.model_copy(update={"right": plan.right.model_copy(update={"track": "upstream"})})
    with pytest.raises(StateError, match="track"):
        validate_plan(mixed)


def test_cli_freezes_plan_and_writes_comparison_without_overwriting(
    tmp_path, protocol, task, monkeypatch, capsys
):
    from graybench import cli
    from graybench.campaign_setup import build_setup
    from graybench.comparison import ComparisonPlan
    from graybench.identity import canonical

    _, tasks = setup(protocol, task)

    def selected(suite, *_args, **_kwargs):
        return tasks if suite == "hard" else ()

    monkeypatch.setattr("graybench.campaign_setup.load_suite", selected)
    monkeypatch.setattr("graybench.cli.load_suite", selected)
    image = "sha256:" + "a" * 64
    a = build_setup("left", protocol.model, tasks, image)
    b = build_setup("right", protocol.model.model_copy(update={"model": "other"}), tasks, image)
    left_setup, right_setup, plan_file, output = (
        tmp_path / name for name in ("left.json", "right.json", "plan.json", "report.json")
    )
    left_setup.write_bytes(canonical(a.model_dump(mode="json")))
    right_setup.write_bytes(canonical(b.model_dump(mode="json")))
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "comparison-plan",
            str(left_setup),
            str(right_setup),
            str(tmp_path),
            str(plan_file),
            "--seed",
            "5",
            "--resamples",
            "1000",
            "--configuration-comparison",
            "Synthetic fixtures only",
        ],
    )
    cli.main()
    plan = ComparisonPlan.model_validate_json(plan_file.read_bytes())
    left_path, right_path = tmp_path / "left.sqlite", tmp_path / "right.sqlite"
    left, right = Ledger(left_path), Ledger(right_path)
    try:
        left_run = fill(left, plan.left, tasks, ["pass", "fail", "pass"])
        right_run = fill(right, plan.right, tasks, ["fail", "pass", "fail"])
    finally:
        left.close()
        right.close()
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "compare",
            str(plan_file),
            str(left_path),
            left_run,
            str(right_path),
            right_run,
            str(tmp_path),
            str(output),
        ],
    )
    cli.main()
    original = output.read_bytes()
    assert b'"status":"development_only"' in original
    with pytest.raises(FileExistsError):
        cli.main()
    assert output.read_bytes() == original
    capsys.readouterr()


def _exercise_track_cli(left_setup, right_setup, cache, tmp_path, monkeypatch, capsys):
    from graybench import cli
    from graybench.campaign_setup import execution_context
    from graybench.comparison import ComparisonPlan
    from graybench.identity import canonical

    left_path, right_path, plan_path, report_path = (
        tmp_path / name for name in ("left.json", "right.json", "plan.json", "report.json")
    )
    left_path.write_bytes(canonical(left_setup.model_dump(mode="json")))
    right_path.write_bytes(canonical(right_setup.model_dump(mode="json")))
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "comparison-plan",
            str(left_path),
            str(right_path),
            str(cache),
            str(plan_path),
            "--seed",
            "5",
            "--resamples",
            "1000",
            "--configuration-comparison",
            "Synthetic local setups; no provider equivalence claim",
        ],
    )
    cli.main()
    plan = ComparisonPlan.model_validate_json(plan_path.read_bytes())
    assert plan.left.track == left_setup.protocol.track
    assert plan.right.track == right_setup.protocol.track
    capsys.readouterr()
    left_ledger_path, right_ledger_path = (
        tmp_path / name for name in ("left.sqlite", "right.sqlite")
    )
    books = (Ledger(left_ledger_path), Ledger(right_ledger_path))
    try:
        left_run = books[0].create_run(left_setup.protocol, execution_context(left_setup))
        right_run = books[1].create_run(right_setup.protocol, execution_context(right_setup))
    finally:
        for book in books:
            book.close()
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "compare",
            str(plan_path),
            str(left_ledger_path),
            left_run,
            str(right_ledger_path),
            right_run,
            str(cache),
            str(report_path),
        ],
    )
    cli.main()
    report = __import__("json").loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "unscored"
    assert report["comparison"] is None
    assert report["publication_eligible"] is False
    original = report_path.read_bytes()
    with pytest.raises(FileExistsError):
        cli.main()
    assert report_path.read_bytes() == original
    capsys.readouterr()


def test_native_cli_comparison_uses_frozen_setup(tmp_path, monkeypatch, capsys):
    from test_native_campaign import native_setup
    from test_native_cohort import cache as synthetic_cache

    cache = synthetic_cache.__wrapped__(tmp_path / "cache", monkeypatch)
    left = native_setup(cache)
    right = native_setup(cache)
    _exercise_track_cli(left, right, cache, tmp_path, monkeypatch, capsys)


@pytest.mark.skipif(not PINNED_CACHE, reason="Pinned source cache required")
def test_protected_cli_comparison_uses_frozen_setup(tmp_path, monkeypatch, capsys):
    from test_protected_campaign import two_task_setup

    left = two_task_setup()
    right = two_task_setup()
    _exercise_track_cli(left, right, Path(PINNED_CACHE), tmp_path, monkeypatch, capsys)


def test_comparison_cli_rejects_mixed_setup_kinds(tmp_path, monkeypatch):
    from test_native_campaign import native_setup
    from test_native_cohort import IMAGE
    from test_native_cohort import cache as synthetic_cache

    from graybench import cli
    from graybench.campaign_setup import build_setup
    from graybench.identity import canonical

    cache = synthetic_cache.__wrapped__(tmp_path / "cache", monkeypatch)
    native = native_setup(cache)
    historical = build_setup("historical", native.protocol.model, native.tasks(cache), IMAGE)
    left, right, output = (tmp_path / name for name in ("left.json", "right.json", "plan.json"))
    left.write_bytes(canonical(native.model_dump(mode="json")))
    right.write_bytes(canonical(historical.model_dump(mode="json")))
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "comparison-plan",
            str(left),
            str(right),
            str(cache),
            str(output),
            "--seed",
            "5",
            "--configuration-comparison",
            "Must reject mixed tracks",
        ],
    )
    with pytest.raises(StateError, match="track"):
        cli.main()
    assert not output.exists()


def test_native_compare_rejects_altered_stored_context(tmp_path, monkeypatch, capsys):
    from test_native_campaign import native_setup
    from test_native_cohort import cache as synthetic_cache

    from graybench import cli
    from graybench.campaign_setup import execution_context
    from graybench.identity import canonical

    cache = synthetic_cache.__wrapped__(tmp_path / "cache", monkeypatch)
    frozen = native_setup(cache)
    setup_paths = [tmp_path / name for name in ("left.json", "right.json")]
    for path in setup_paths:
        path.write_bytes(canonical(frozen.model_dump(mode="json")))
    plan_path = tmp_path / "plan.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "comparison-plan",
            *(str(path) for path in setup_paths),
            str(cache),
            str(plan_path),
            "--seed",
            "5",
            "--configuration-comparison",
            "Synthetic local setup",
        ],
    )
    cli.main()
    capsys.readouterr()
    books = [Ledger(tmp_path / name) for name in ("left.sqlite", "right.sqlite")]
    try:
        changed = execution_context(frozen)
        changed["setup"]["cohort"]["label"] = "altered after plan"
        runs = (
            books[0].create_run(frozen.protocol, changed),
            books[1].create_run(frozen.protocol, execution_context(frozen)),
        )
    finally:
        for book in books:
            book.close()
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "compare",
            str(plan_path),
            str(tmp_path / "left.sqlite"),
            runs[0],
            str(tmp_path / "right.sqlite"),
            runs[1],
            str(cache),
            str(report_path),
        ],
    )
    with pytest.raises((StateError, ValueError), match="cohort|setup"):
        cli.main()
    assert not report_path.exists()


@pytest.mark.skipif(
    not PINNED_CACHE or not os.environ.get("GRAYBENCH_TEST_IMAGE"),
    reason="Pinned source cache and Docker image required",
)
def test_completed_protected_comparison_uses_judged_samples(tmp_path, monkeypatch, capsys):
    import httpx
    from test_protected_campaign import MODEL, direct_solution, handler, setup

    from graybench import cli
    from graybench.campaign_setup import execution_context
    from graybench.identity import canonical
    from graybench.protected_campaign import ProtectedCampaign
    from graybench.transport import Transport

    frozen = setup()
    setup_paths = [tmp_path / name for name in ("left.json", "right.json")]
    for path in setup_paths:
        path.write_bytes(canonical(frozen.model_dump(mode="json")))
    plan_path = tmp_path / "plan.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "comparison-plan",
            *(str(path) for path in setup_paths),
            PINNED_CACHE,
            str(plan_path),
            "--seed",
            "5",
            "--resamples",
            "1000",
            "--configuration-comparison",
            "Fixture answers through one pinned protected oracle",
        ],
    )
    cli.main()
    capsys.readouterr()
    runs = []
    for label, answer in (
        ("left", direct_solution()),
        (
            "right",
            "def ghz_amplitudes(layout):\n"
            "    return [[1.0,0.0]] + [[0.0,0.0] for _ in range(127)]\n",
        ),
    ):
        book = Ledger(tmp_path / f"{label}.sqlite")
        try:
            run = book.create_run(frozen.protocol, execution_context(frozen))

            def response(request, answer=answer):
                if request.url.path != "/api/chat":
                    return handler(request)
                return httpx.Response(
                    200,
                    json={
                        "model": "fixture",
                        "done": True,
                        "message": {"role": "assistant", "content": answer},
                    },
                )

            with httpx.Client(transport=httpx.MockTransport(response)) as client:
                campaign = ProtectedCampaign(
                    book, run, frozen, Path(PINNED_CACHE), Transport(MODEL, client=client)
                )
                assert campaign.step()["state"] == "dispatched"
                assert campaign.step()["state"] == "judged"
            assert book.summary(run)["complete"] is True
            runs.append(run)
        finally:
            book.close()
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "compare",
            str(plan_path),
            str(tmp_path / "left.sqlite"),
            runs[0],
            str(tmp_path / "right.sqlite"),
            runs[1],
            PINNED_CACHE,
            str(report_path),
        ],
    )
    cli.main()
    report = __import__("json").loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "development_only"
    assert report["comparison"]["left_minus_right"] == 1
    assert report["comparison"]["interval_unavailable_reason"] == "fewer_than_two_families"
    assert report["publication_eligible"] is False
    capsys.readouterr()


@pytest.mark.skipif(
    not PINNED_CACHE or not os.environ.get("GRAYBENCH_TEST_IMAGE"),
    reason="Pinned source cache and Docker image required",
)
def test_completed_native_comparison_uses_judged_samples(tmp_path, monkeypatch, capsys):
    import httpx
    from test_native_campaign import MODEL

    from graybench import cli
    from graybench.campaign_setup import execution_context
    from graybench.datasets import load_suite
    from graybench.identity import canonical
    from graybench.native_campaign import NativeCampaign, build_native_setup
    from graybench.native_cohort import freeze_native_cohort
    from graybench.transport import Transport

    cache = Path(PINNED_CACHE)
    task = load_suite("normal", cache)[0]
    cohort = freeze_native_cohort(
        (task,),
        cache=cache,
        suite="normal",
        population="custom_development",
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        extraction="raw_or_single_python_fence_v1",
        label="task zero comparison fixture",
        excluded={
            f"normal/qiskitHumanEval/{number}": "out_of_scope_development"
            for number in range(1, 151)
        },
    )
    frozen = build_native_setup("comparison fixture", MODEL, cohort, (task,), cache=cache)
    setup_paths = [tmp_path / name for name in ("left.json", "right.json")]
    for path in setup_paths:
        path.write_bytes(canonical(frozen.model_dump(mode="json")))
    plan_path = tmp_path / "plan.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "comparison-plan",
            *(str(path) for path in setup_paths),
            str(cache),
            str(plan_path),
            "--seed",
            "5",
            "--resamples",
            "1000",
            "--configuration-comparison",
            "Fixture answers through one pinned native oracle",
        ],
    )
    cli.main()
    capsys.readouterr()
    runs = []
    for label, answer in (("left", task.canonical_solution), ("right", "\n    return None\n")):
        book = Ledger(tmp_path / f"{label}.sqlite")
        try:
            run = book.create_run(frozen.protocol, execution_context(frozen))

            def response(request, answer=answer):
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
                        "message": {"role": "assistant", "content": answer},
                    },
                )

            with httpx.Client(transport=httpx.MockTransport(response)) as client:
                campaign = NativeCampaign(book, run, frozen, cache, Transport(MODEL, client=client))
                assert campaign.step()["state"] == "dispatched"
                assert campaign.step()["state"] == "judged"
            assert book.summary(run)["complete"] is True
            runs.append(run)
        finally:
            book.close()
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "graybench",
            "compare",
            str(plan_path),
            str(tmp_path / "left.sqlite"),
            runs[0],
            str(tmp_path / "right.sqlite"),
            runs[1],
            str(cache),
            str(report_path),
        ],
    )
    cli.main()
    report = __import__("json").loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "development_only"
    assert report["comparison"]["left_minus_right"] == 1
    assert report["comparison"]["interval_unavailable_reason"] == "fewer_than_two_families"
    assert report["publication_eligible"] is False
    capsys.readouterr()

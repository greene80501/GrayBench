"""Repeated-sample opportunity metrics cannot replace single-answer reliability."""

from fractions import Fraction
from itertools import combinations

import pytest


def api():
    from graybench import sample_metrics

    return sample_metrics


def fixture(protocol, task, repeats=3):
    from test_comparison import setup

    paired, tasks = setup(protocol, task)
    return paired.left.model_copy(update={"repeats": repeats}), tasks


def test_exact_estimator_agrees_with_enumerated_candidate_subsets():
    for n in range(1, 9):
        for c in range(n + 1):
            for k in range(1, n + 1):
                subsets = list(combinations(range(n), k))
                successes = sum(any(index < c for index in selected) for selected in subsets)
                assert api().pass_at_k_fraction(n, c, k) == Fraction(successes, len(subsets))


@pytest.mark.parametrize(
    "n,c,k",
    [
        (True, 1, 1),
        (3, False, 1),
        (3, 1, True),
        (0, 0, 1),
        (3, -1, 1),
        (3, 4, 1),
        (3, 1, 0),
        (3, 1, 4),
        (1001, 1, 1),
    ],
)
def test_estimator_rejects_invalid_counts_and_insufficient_samples(n, c, k):
    with pytest.raises(ValueError):
        api().pass_at_k_fraction(n, c, k)


def test_plan_binds_tasks_source_and_all_k_before_analysis(protocol, task):
    protocol, tasks = fixture(protocol, task)
    plan = api().make_metrics_plan(protocol, tasks, ks=(3, 2))
    assert plan.ks == (1, 2, 3)
    assert len(set(plan.families.values())) == 2  # Related records remain in one breakdown.
    for ks in ((1, 4), (1, 1), (True,), (0,)):
        with pytest.raises(ValueError):
            api().make_metrics_plan(protocol, tasks, ks=ks)
    changed = tasks[0].model_copy(
        update={"public": tasks[0].public.model_copy(update={"family_id": "other"})}
    )
    with pytest.raises(ValueError):
        api().make_metrics_plan(protocol, (changed, *tasks[1:]), ks=(1, 2))
    for field, value in (("ks", (2,)), ("method", "wrong"), ("analysis_source", "0" * 64)):
        with pytest.raises(ValueError):
            api().validate_metrics_plan(plan.model_copy(update={field: value}))


def fraction(record):
    return Fraction(int(record["numerator_hex"], 16), int(record["denominator_hex"], 16))


def test_verified_repeated_ledger_scores_every_task_without_best_answer_selection(
    tmp_path, protocol, task
):
    from copy import deepcopy

    from test_comparison import fill

    from graybench.ledger import Ledger

    protocol, tasks = fixture(protocol, task)
    plan = api().make_metrics_plan(protocol, tasks, ks=(2, 3))
    book = Ledger(tmp_path / "book.sqlite")
    try:
        run = fill(
            book,
            protocol,
            tasks,
            ["pass", "pass", "fail", "fail", "timeout", "candidate_error", "pass", "fail", "fail"],
        )
        report = api().sample_metrics_report(plan, book, run, tasks=tasks)
        assert report["status"] == "development_only"
        assert fraction(report["metrics"]["pass@1"]) == Fraction(1, 3)
        assert report["metrics"]["pass@1"]["float_value"] == report["run"]["pass_at_1"]
        assert fraction(report["metrics"]["pass@2"]) == Fraction(5, 9)
        assert fraction(report["metrics"]["pass@3"]) == Fraction(2, 3)
        assert len(report["per_task_metrics"]) == 3
        assert len(report["family_metrics"]) == 2
        # Families are descriptive breakdowns; two related records must not receive
        # the same global weight as a single record under the frozen equal-task policy.
        families = report["family_metrics"]
        assert fraction(families[0]["metrics"]["pass@1"]) == Fraction(1, 3)
        assert fraction(families[1]["metrics"]["pass@1"]) == Fraction(1, 3)
        assert report["publication_eligible"] is False
        assert api().verify_sample_metrics(report, plan, book, run, tasks=tasks)["verified"]
        modified = deepcopy(report)
        modified["metrics"]["pass@3"]["float_value"] = 1.0
        with pytest.raises(ValueError, match="replay"):
            api().verify_sample_metrics(modified, plan, book, run, tasks=tasks)
        incomplete = fill(
            book,
            protocol,
            tasks,
            ["pass", "pass", "fail", "fail", "unsupported", "fail", "pass", "fail", "fail"],
        )
        unscored = api().sample_metrics_report(plan, book, incomplete, tasks=tasks)
        assert unscored["status"] == "unscored"
        assert unscored["metrics"] is None
        assert unscored["per_task_metrics"] is None
        assert unscored["family_metrics"] is None
        assert api().verify_sample_metrics(unscored, plan, book, incomplete, tasks=tasks)[
            "verified"
        ]
    finally:
        book.close()


def test_calibration_rejects_unreviewed_source_before_execution(tmp_path):
    import importlib.util
    from pathlib import Path

    script = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/sample_metrics_calibration.py"
    )
    spec = importlib.util.spec_from_file_location("sample_metric_calibration", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sentinel = tmp_path / "untrusted-executed"
    untrusted = tmp_path / "reference.py"
    untrusted.write_text(f"open({str(sentinel)!r}, 'w').write('executed')", encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed HumanEval source"):
        module.numeric_reference(untrusted)
    assert not sentinel.exists()


def test_family_breakdowns_preserve_unequal_task_counts(tmp_path, protocol, task):
    from test_comparison import fill

    from graybench.ledger import Ledger

    protocol, tasks = fixture(protocol, task, repeats=1)
    plan = api().make_metrics_plan(protocol, tasks)
    book = Ledger(tmp_path / "book.sqlite")
    try:
        run = fill(book, protocol, tasks, ["pass", "pass", "fail"])
        report = api().sample_metrics_report(plan, book, run, tasks=tasks)
        assert fraction(report["metrics"]["pass@1"]) == Fraction(2, 3)
        assert [row["task_count"] for row in report["family_metrics"]] == [2, 1]
        assert [fraction(row["metrics"]["pass@1"]) for row in report["family_metrics"]] == [1, 0]
    finally:
        book.close()


def test_cli_freezes_repeats_and_metrics_then_replays_readonly_evidence(
    tmp_path, protocol, task, monkeypatch, capsys
):
    import json

    from test_comparison import fill

    from graybench import cli
    from graybench.campaign_setup import build_setup
    from graybench.identity import canonical
    from graybench.ledger import Ledger

    _, tasks = fixture(protocol, task)

    def selected(suite, *_args, **_kwargs):
        return tasks if suite == "hard" else ()

    monkeypatch.setattr("graybench.campaign_setup.load_suite", selected)
    monkeypatch.setattr("graybench.cli.load_suite", selected)
    frozen = build_setup("metric fixture", protocol.model, tasks, "sha256:" + "a" * 64, repeats=3)
    setup_file, plan_file, report_file, book_file = (
        tmp_path / name for name in ("setup.json", "plan.json", "report.json", "book.sqlite")
    )
    setup_file.write_bytes(canonical(frozen.model_dump(mode="json")))

    def invoke(*args):
        monkeypatch.setattr("sys.argv", ["graybench", *map(str, args)])
        cli.main()
        return json.loads(capsys.readouterr().out)

    output = invoke("metrics-plan", setup_file, tmp_path, plan_file, "--k", 2, "--k", 3)
    assert output["ks"] == [1, 2, 3]
    plan = api().SampleMetricsPlan.model_validate_json(plan_file.read_bytes())
    book = Ledger(book_file)
    try:
        run = fill(
            book,
            plan.protocol,
            tasks,
            ["pass", "pass", "fail", "fail", "fail", "fail", "pass", "fail", "fail"],
        )
    finally:
        book.close()
    before = book_file.read_bytes()
    result = invoke("metrics", plan_file, book_file, run, tmp_path, report_file)
    assert result["status"] == "development_only"
    assert fraction(result["metrics"]["pass@2"]) == Fraction(5, 9)
    assert invoke("metrics-verify", plan_file, book_file, run, tmp_path, report_file)["verified"]
    assert book_file.read_bytes() == before
    original = report_file.read_bytes()
    with pytest.raises(FileExistsError):
        invoke("metrics", plan_file, book_file, run, tmp_path, report_file)
    assert report_file.read_bytes() == original
    report_file.write_bytes(b"null")
    with pytest.raises(ValueError, match="replay"):
        invoke("metrics-verify", plan_file, book_file, run, tmp_path, report_file)
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(ValueError, match="exist"):
        invoke("metrics", plan_file, missing, run, tmp_path, tmp_path / "missing-report.json")
    assert not missing.exists()
    assert not (tmp_path / "missing-report.json").exists()


@pytest.mark.parametrize("track", ["native", "protected"])
def test_track_metric_cli_validates_context_and_retains_incomplete_cohort(
    track, tmp_path, monkeypatch, capsys
):
    import json
    import os
    from pathlib import Path

    from graybench import cli
    from graybench.campaign_setup import execution_context
    from graybench.identity import canonical
    from graybench.ledger import Ledger

    if track == "native":
        from test_native_campaign import native_setup
        from test_native_cohort import cache as synthetic_cache

        cache = synthetic_cache.__wrapped__(tmp_path / "cache", monkeypatch)
        frozen = native_setup(cache)
    else:
        from test_protected_campaign import two_task_setup

        if not os.environ.get("GRAYBENCH_TEST_CACHE"):
            pytest.skip("Pinned source cache required")
        cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
        frozen = two_task_setup()
    setup_path, plan_path, book_path, report_path = (
        tmp_path / name for name in ("setup.json", "plan.json", "book.sqlite", "report.json")
    )
    setup_path.write_bytes(canonical(frozen.model_dump(mode="json")))

    def invoke(*args):
        monkeypatch.setattr("sys.argv", ["graybench", *map(str, args)])
        cli.main()
        return json.loads(capsys.readouterr().out)

    assert invoke("metrics-plan", setup_path, cache, plan_path)["ks"] == [1]
    book = Ledger(book_path)
    try:
        run = book.create_run(frozen.protocol, execution_context(frozen))
        changed = execution_context(frozen)
        changed["setup"]["cohort"]["label"] = "changed after freezing"
        bad = book.create_run(frozen.protocol, changed)
    finally:
        book.close()
    result = invoke("metrics", plan_path, book_path, run, cache, report_path)
    assert result["status"] == "unscored"
    assert result["metrics"] is None
    assert invoke("metrics-verify", plan_path, book_path, run, cache, report_path)["verified"]
    with pytest.raises(ValueError, match="cohort|setup"):
        invoke("metrics", plan_path, book_path, bad, cache, tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()


def test_same_math_does_not_allow_changed_protocol_run_or_family_binding(tmp_path, protocol, task):
    from test_comparison import fill

    from graybench.ledger import Ledger

    protocol, tasks = fixture(protocol, task, repeats=1)
    plan = api().make_metrics_plan(protocol, tasks)
    book = Ledger(tmp_path / "book.sqlite")
    try:
        run = fill(book, protocol, tasks, ["pass", "pass", "fail"])
        changed = plan.model_copy(update={"families": {key: "different" for key in plan.families}})
        with pytest.raises(ValueError, match="family mapping"):
            api().sample_metrics_report(changed, book, run, tasks=tasks)
        other = fill(
            book,
            protocol.model_copy(update={"name": "different run protocol"}),
            tasks,
            ["pass", "pass", "fail"],
        )
        with pytest.raises(ValueError, match="protocol"):
            api().sample_metrics_report(plan, book, other, tasks=tasks)
        assert not book.db.in_transaction
    finally:
        book.close()

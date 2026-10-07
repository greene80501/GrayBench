"""Exact paired binary analysis is separate from repeated/family bootstrap."""

from fractions import Fraction

import pytest


def api():
    from graybench import binary_comparison

    return binary_comparison


def test_exact_mcnemar_retains_rational_probability_and_discordant_direction():
    result = api().exact_mcnemar(8, 1)
    assert result == Fraction(5, 128)
    assert api().exact_mcnemar(1, 8) == result
    assert api().exact_mcnemar(0, 0) == 1
    assert api().exact_mcnemar(5, 5) == 1


@pytest.mark.parametrize("left,right", [(True, 1), (-1, 1), (1.0, 1), (1, False)])
def test_discordance_counts_are_strict_nonnegative_integers(left, right):
    with pytest.raises(ValueError, match="counts"):
        api().exact_mcnemar(left, right)


def test_holm_is_monotone_and_preserves_exact_threshold_comparison():
    adjusted = api().holm_adjust(
        {"a": Fraction(1, 100), "b": Fraction(4, 100), "c": Fraction(3, 100)}
    )
    assert adjusted == {"a": Fraction(3, 100), "b": Fraction(6, 100), "c": Fraction(6, 100)}
    tiny = api().exact_mcnemar(2000, 0)
    record = api().probability_record(tiny)
    assert record["float_underflow"] is True
    assert Fraction(int(record["numerator_hex"], 16), int(record["denominator_hex"], 16)) == tiny
    assert api().holm_adjust({"a": tiny, "b": tiny})["a"] == 2 * tiny


def test_binary_plan_refuses_repeat_or_family_pseudoreplication(protocol, task):
    from test_comparison import setup

    pair, tasks = setup(protocol, task)
    with pytest.raises(ValueError, match="one.*family"):
        api().make_binary_plan(
            pair.left,
            pair.right,
            tasks,
            configuration_comparison="fixture",
            independence_basis="synthetic families",
        )
    unique = tuple(
        t.model_copy(update={"public": t.public.model_copy(update={"family_id": str(i)})})
        for i, t in enumerate(tasks)
    )
    # These mutated records no longer match the original frozen dataset.
    with pytest.raises(ValueError):
        api().make_binary_plan(
            pair.left,
            pair.right,
            unique,
            configuration_comparison="fixture",
            independence_basis="synthetic families",
        )


def binary_fixture(protocol, task):
    from test_comparison import setup

    from graybench.identity import identity
    from graybench.providers import Ollama

    paired, old = setup(protocol, task)
    tasks = tuple(
        t.model_copy(update={"public": t.public.model_copy(update={"family_id": f"fixture/{i}"})})
        for i, t in enumerate(old)
    )
    keyed = {f"{t.public.suite}/{t.public.task_id}": t for t in tasks}
    protocols = [
        p.model_copy(
            update={
                "dataset_digest": identity({k: t.digest for k, t in keyed.items()}),
                "request_digests": {
                    k: Ollama().prepare(p.model, t.public, None).digest for k, t in keyed.items()
                },
            }
        )
        for p in (paired.left, paired.right)
    ]
    plan = api().make_binary_plan(
        *protocols,
        tasks,
        configuration_comparison="Synthetic protocol fixture",
        independence_basis="Distinct artificial fixture families; not real task evidence",
    )
    return plan, tasks


def test_repeats_and_changed_family_binding_are_rejected(protocol, task):
    plan, tasks = binary_fixture(protocol, task)
    for changed in (
        plan.model_copy(
            update={
                "left": plan.left.model_copy(update={"repeats": 2}),
                "right": plan.right.model_copy(update={"repeats": 2}),
            }
        ),
        plan.model_copy(update={"families": {key: "same" for key in plan.families}}),
    ):
        with pytest.raises(ValueError, match="one"):
            api().validate_binary_plan(changed)


def test_real_ledger_pair_counts_and_complete_study_use_every_planned_contrast(
    tmp_path, protocol, task
):
    from test_comparison import fill

    from graybench.ledger import Ledger
    from graybench.providers import Ollama

    plan, tasks = binary_fixture(protocol, task)
    third_model = plan.right.model.model_copy(update={"model": "third-model"})
    third = plan.right.model_copy(
        update={
            "model": third_model,
            "request_digests": {
                f"{t.public.suite}/{t.public.task_id}": Ollama()
                .prepare(third_model, t.public, None)
                .digest
                for t in tasks
            },
        }
    )
    other = api().make_binary_plan(
        plan.left,
        third,
        tasks,
        configuration_comparison="Other synthetic pair",
        independence_basis=plan.independence_basis,
    )
    study = api().make_binary_study(
        [
            api().BinaryContrast(contrast_id="ab", plan=plan),
            api().BinaryContrast(contrast_id="ac", plan=other),
        ],
        purpose="Synthetic arithmetic and ledger wiring",
    )
    books = [Ledger(tmp_path / name) for name in ("a.sqlite", "b.sqlite", "c.sqlite")]
    try:
        runs = [
            fill(books[0], plan.left, tasks, ["pass", "pass", "fail"]),
            fill(books[1], plan.right, tasks, ["fail", "fail", "pass"]),
            fill(books[2], third, tasks, ["fail", "fail", "fail"]),
        ]
        inputs = {
            "ab": (books[0], runs[0], books[1], runs[1]),
            "ac": (books[0], runs[0], books[2], runs[2]),
        }
        report = api().compare_binary_study(study, inputs, tasks={"ab": tasks, "ac": tasks})
        assert report["status"] == "development_only"
        assert report["contrasts"]["ab"]["comparison"]["counts"] == {
            "both_pass": 0,
            "left_only": 2,
            "right_only": 1,
            "both_not_pass": 0,
        }
        assert report["contrasts"]["ab"]["comparison"]["left_minus_right"] == pytest.approx(1 / 3)
        assert report["contrasts"]["ac"]["comparison"]["exact_p"]["float_value"] == 0.5
        assert all(r["adjusted_p"]["float_value"] == 1 for r in report["holm"].values())
        assert not report["publication_eligible"]
        pair_report = report["contrasts"]["ab"]
        assert "Bernoulli(1/2)" in pair_report["comparison"]["conditional_null"]
        assert any("aggregate finite-cohort rates" in text for text in pair_report["limitations"])
        assert api().verify_binary_study(
            report, study, inputs, tasks={"ab": tasks, "ac": tasks}
        ) == {
            "verified": True,
            "plan_digest": study.digest,
            "status": "development_only",
            "publication_eligible": False,
        }
        from copy import deepcopy

        tampered = deepcopy(report)
        tampered["holm"]["ac"]["reject_equal_marginals"] = True
        with pytest.raises(ValueError, match="replay"):
            api().verify_binary_study(tampered, study, inputs, tasks={"ab": tasks, "ac": tasks})
        with pytest.raises(ValueError, match="every planned"):
            api().compare_binary_study(study, {"ab": inputs["ab"]}, tasks={"ab": tasks})
        incomplete = fill(books[2], third, tasks, ["pass", "unsupported", "fail"])
        inputs["ac"] = (books[0], runs[0], books[2], incomplete)
        withheld = api().compare_binary_study(study, inputs, tasks={"ab": tasks, "ac": tasks})
        assert withheld["status"] == "unscored"
        assert withheld["holm"] is None
        assert withheld["contrasts"]["ab"]["comparison"] is not None
        assert withheld["contrasts"]["ac"]["comparison"] is None
        assert api().verify_binary_study(withheld, study, inputs, tasks={"ab": tasks, "ac": tasks})[
            "verified"
        ]
    finally:
        for book in books:
            book.close()


def test_exact_tail_matches_scipy_independent_implementation_for_a_grid():
    scipy = pytest.importorskip("scipy.stats")
    for left in range(31):
        for right in range(31):
            expected = (
                1
                if left + right == 0
                else scipy.binomtest(left, left + right, 0.5, alternative="two-sided").pvalue
            )
            assert float(api().exact_mcnemar(left, right)) == pytest.approx(
                expected, abs=1e-14, rel=1e-14
            )


def test_study_rejects_duplicate_ids_and_reversed_duplicate_protocol_pairs(protocol, task):
    plan, _ = binary_fixture(protocol, task)
    reverse = plan.model_copy(update={"left": plan.right, "right": plan.left})
    with pytest.raises(ValueError, match="unique"):
        api().make_binary_study(
            [
                api().BinaryContrast(contrast_id="ab", plan=plan),
                api().BinaryContrast(contrast_id="ba", plan=reverse),
            ],
            purpose="Fixture",
        )


def test_readonly_analysis_ledger_cannot_create_or_modify(tmp_path, protocol):
    import sqlite3

    from graybench.ledger import Ledger

    path = tmp_path / "book.sqlite"
    with pytest.raises(FileNotFoundError):
        Ledger(path, readonly=True)
    assert not path.exists()
    book = Ledger(path)
    run = book.create_run(protocol)
    book.close()
    original = path.read_bytes()
    readonly = Ledger(path, readonly=True)
    try:
        assert readonly.protocol(run) == protocol
        readonly.verify()
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            readonly.create_run(protocol)
    finally:
        readonly.close()
    assert path.read_bytes() == original


def test_cli_binary_study_freeze_replay_verify_and_refuse_partial_inputs(
    tmp_path, protocol, task, monkeypatch, capsys
):
    import json

    from test_comparison import fill

    from graybench import cli
    from graybench.campaign_setup import build_setup
    from graybench.identity import canonical
    from graybench.ledger import Ledger

    _, tasks = binary_fixture(protocol, task)

    def selected(suite, *_args, **_kwargs):
        return tasks if suite == "hard" else ()

    monkeypatch.setattr("graybench.campaign_setup.load_suite", selected)
    monkeypatch.setattr("graybench.cli.load_suite", selected)
    setups = [
        build_setup(
            name, protocol.model.model_copy(update={"model": name}), tasks, "sha256:" + "a" * 64
        )
        for name in ("a", "b")
    ]
    for name, setup in zip(("a", "b"), setups, strict=True):
        (tmp_path / f"{name}.json").write_bytes(canonical(setup.model_dump(mode="json")))

    def invoke(*args):
        monkeypatch.setattr("sys.argv", ["graybench", *map(str, args)])
        cli.main()
        return json.loads(capsys.readouterr().out)

    pair_path, study_path, report_path = (
        tmp_path / name for name in ("pair.json", "study.json", "report.json")
    )
    invoke(
        "binary-comparison-plan",
        tmp_path / "a.json",
        tmp_path / "b.json",
        tmp_path,
        pair_path,
        "--configuration-comparison",
        "Synthetic setups",
        "--independence-basis",
        "Artificial independent fixture families",
    )
    pair = api().BinaryComparisonPlan.model_validate_json(pair_path.read_bytes())
    definitions = tmp_path / "contrasts.json"
    definitions.write_bytes(canonical({"ab": "pair.json"}))
    invoke("binary-study-plan", definitions, study_path, "--purpose", "Synthetic end-to-end replay")
    inputs = {}
    for name, expected, outcomes in (
        ("a", pair.left, ["pass", "fail", "pass"]),
        ("b", pair.right, ["fail", "pass", "fail"]),
    ):
        book = Ledger(tmp_path / f"{name}.sqlite")
        try:
            inputs[name] = fill(book, expected, tasks, outcomes)
        finally:
            book.close()
    run_path = tmp_path / "runs.json"
    run_path.write_bytes(
        canonical(
            {
                "ab": {
                    "left_ledger": "a.sqlite",
                    "left_run": inputs["a"],
                    "right_ledger": "b.sqlite",
                    "right_run": inputs["b"],
                }
            }
        )
    )
    original_books = [(tmp_path / f"{name}.sqlite").read_bytes() for name in ("a", "b")]
    output = invoke("binary-study", study_path, run_path, tmp_path, report_path)
    assert output["status"] == "development_only"
    assert invoke("binary-study-verify", study_path, run_path, tmp_path, report_path)["verified"]
    original_report = report_path.read_bytes()
    with pytest.raises(FileExistsError):
        invoke("binary-study", study_path, run_path, tmp_path, report_path)
    assert report_path.read_bytes() == original_report
    assert original_books == [(tmp_path / f"{name}.sqlite").read_bytes() for name in ("a", "b")]
    tampered = json.loads(original_report)
    tampered["contrasts"]["ab"]["comparison"]["counts"]["left_only"] = 0
    report_path.write_bytes(canonical(tampered))
    with pytest.raises(ValueError, match="replay"):
        invoke("binary-study-verify", study_path, run_path, tmp_path, report_path)
    report_path.write_bytes(b"null")
    with pytest.raises(ValueError, match="replay"):
        invoke("binary-study-verify", study_path, run_path, tmp_path, report_path)
    run_path.write_bytes(canonical({}))
    with pytest.raises(ValueError, match="every planned"):
        invoke("binary-study", study_path, run_path, tmp_path, tmp_path / "missing.json")
    assert not (tmp_path / "missing.json").exists()


@pytest.mark.parametrize(
    "payload", [b'{"ab": 1, "ab": 2}', b'{"ab":{"x":1,"x":2}}', b'{"ab": NaN}']
)
def test_binary_json_refuses_duplicate_fields_and_nonfinite_extensions(payload):
    with pytest.raises(ValueError):
        api().load_binary_json(payload)


def test_binary_runtime_validation_rejects_model_copy_bypass(protocol, task):
    plan, _ = binary_fixture(protocol, task)
    with pytest.raises(ValueError):
        api().validate_binary_plan(plan.model_copy(update={"method": "wrong"}))
    study = api().make_binary_study(
        [api().BinaryContrast(contrast_id="ab", plan=plan)], purpose="Fixture"
    )
    for field, value in (("method", "wrong"), ("alpha", float("nan")), ("purpose", " ")):
        with pytest.raises(ValueError):
            api().validate_binary_study(study.model_copy(update={field: value}))


def test_analysis_bound_and_probability_validation_are_explicit():
    assert api().exact_mcnemar(5000, 5000) == 1
    assert api().probability_record(api().exact_mcnemar(10000, 0))["float_underflow"]
    with pytest.raises(ValueError, match="bound"):
        api().exact_mcnemar(10001, 0)
    for value in (True, 0.05, Fraction(-1), Fraction(2)):
        with pytest.raises(ValueError, match="probability"):
            api().probability_record(value)


@pytest.mark.parametrize("track", ["native", "protected"])
def test_binary_cli_uses_frozen_track_context_and_withholds_incomplete_results(
    track, tmp_path, monkeypatch, capsys
):
    import json

    from test_native_cohort import cache as synthetic_cache

    from graybench import cli
    from graybench.campaign_setup import execution_context
    from graybench.identity import canonical
    from graybench.ledger import Ledger

    if track == "native":
        from test_native_campaign import native_setup

        cache = synthetic_cache.__wrapped__(tmp_path / "cache", monkeypatch)
        frozen = native_setup(cache)
    else:
        import os
        from pathlib import Path

        from test_protected_campaign import two_task_setup

        if not os.environ.get("GRAYBENCH_TEST_CACHE"):
            pytest.skip("Pinned source cache required")
        cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
        frozen = two_task_setup()
    for name in ("a", "b"):
        (tmp_path / f"{name}.json").write_bytes(canonical(frozen.model_dump(mode="json")))

    def invoke(*args):
        monkeypatch.setattr("sys.argv", ["graybench", *map(str, args)])
        cli.main()
        return json.loads(capsys.readouterr().out)

    pair_path, study_path, report_path = (
        tmp_path / name for name in ("pair.json", "study.json", "report.json")
    )
    invoke(
        "binary-comparison-plan",
        tmp_path / "a.json",
        tmp_path / "b.json",
        cache,
        pair_path,
        "--configuration-comparison",
        "Identical synthetic setups",
        "--independence-basis",
        "Synthetic fixture declaration only",
    )
    pair = api().BinaryComparisonPlan.model_validate_json(pair_path.read_bytes())
    study = api().make_binary_study(
        [api().BinaryContrast(contrast_id="ab", plan=pair)], purpose="Track context fixture"
    )
    study_path.write_bytes(canonical(study.model_dump(mode="json")))
    rows = {}
    for name in ("a", "b"):
        book = Ledger(tmp_path / f"{name}.sqlite")
        try:
            rows[name] = book.create_run(frozen.protocol, execution_context(frozen))
        finally:
            book.close()
    inputs_path = tmp_path / "runs.json"
    inputs_path.write_bytes(
        canonical(
            {
                "ab": {
                    "left_ledger": "a.sqlite",
                    "left_run": rows["a"],
                    "right_ledger": "b.sqlite",
                    "right_run": rows["b"],
                }
            }
        )
    )
    report = invoke("binary-study", study_path, inputs_path, cache, report_path)
    assert report["status"] == "unscored"
    assert report["holm"] is None
    assert invoke("binary-study-verify", study_path, inputs_path, cache, report_path)["verified"]
    # A valid-looking protocol cannot hide a changed stored setup/cohort.
    bad = execution_context(frozen)
    bad["setup"]["cohort"]["label"] = "tampered"
    book = Ledger(tmp_path / "a.sqlite")
    try:
        bad_run = book.create_run(frozen.protocol, bad)
    finally:
        book.close()
    raw = json.loads(inputs_path.read_bytes())
    raw["ab"]["left_run"] = bad_run
    inputs_path.write_bytes(canonical(raw))
    with pytest.raises(ValueError, match="cohort|setup"):
        invoke("binary-study", study_path, inputs_path, cache, tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()

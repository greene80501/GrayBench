"""Task 62's protected value revision must test both BB84 inputs."""

import json
import os
import sys
from itertools import product
from math import sqrt
from pathlib import Path

import pytest
from pydantic import ValidationError

from graybench.cli import main
from graybench.contracts import ModelSpec
from graybench.datasets import load_suite
from graybench.protected_campaign import build_protected_setup, freeze_protected_cohort
from graybench.protected_oracle_review import protected_probes, run_protected_review
from graybench.protected_semantic_judge import (
    ProtectedSemanticJudge,
    ProtectedSemanticTask,
    SemanticCase,
    _task62_bb84_value,
)
from graybench.protected_task62 import TASK62_SOURCE_DIGESTS, task62_value_task
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_contract import ValueCall
from graybench.protected_value_runner import ValueExecution, ValueRunner

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")


def source(suite="normal"):
    if not CACHE:
        pytest.skip("Pinned source cache required")
    return load_suite(suite, Path(CACHE))[62]


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_contract_freezes_distinct_normal_and_hard_prompts_and_pinned_ancestry():
    for suite in ("normal", "hard"):
        pinned = source(suite)
        task = task62_value_task(pinned)
        assert isinstance(task, ProtectedSemanticTask)
        assert task.contract.source_task_digest == pinned.digest == TASK62_SOURCE_DIGESTS[suite]
        assert task.contract.public.digest != pinned.public.digest
        assert task.contract.public.entry_point == "bb84_sender_amplitudes"
        assert task.contract.public.prompt_format == (
            "function_completion" if suite == "normal" else "standalone_function"
        )
        assert task.contract.track == "graybench-protected-semantic-v1"
        assert task.release_eligible is False
        assert revised_value_task(pinned) == task
        assert revised_value_task(pinned, oracle=task.oracle) == task
        with pytest.raises(ValueError, match="pinned QHE task-62"):
            task62_value_task(pinned.model_copy(update={"canonical_solution": "altered"}))


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_cases_exhaust_small_binary_inputs_and_vary_larger_widths():
    task = task62_value_task(source())
    assert len(task.cases) == 124
    pairs = [(case.call.args[0], case.call.args[1]) for case in task.cases]
    assert len({case.call.digest for case in task.cases}) == 124
    assert all(not case.call.kwargs for case in task.cases)
    assert all(
        len(state) == len(basis) and 1 <= len(state) <= 5 and set(state + basis) <= {0, 1}
        for state, basis in pairs
    )
    for width in (1, 2, 3):
        expected = set(product(product((0, 1), repeat=width), repeat=2))
        observed = {(tuple(state), tuple(basis)) for state, basis in pairs if len(state) == width}
        assert observed == expected
    assert {len(state) for state, _ in pairs} == {1, 2, 3, 4, 5}
    assert ([0, 1, 1, 1, 0], [1, 0, 0, 1, 0]) in pairs


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_result_shape_accepts_only_bounded_numeric_amplitude_pairs():
    task = task62_value_task(source())
    shape = task.contract.result
    assert shape.kind == "array"
    assert (shape.min_items, shape.max_items) == (2, 32)
    assert shape.item.kind == "array"
    assert (shape.item.min_items, shape.item.max_items) == (2, 2)
    assert shape.item.item.kind == "number"
    assert (shape.item.item.minimum, shape.item.item.maximum) == (-1.0, 1.0)


@pytest.mark.parametrize(
    "state,basis,expected",
    [
        ([0], [0], [1.0, 0.0]),
        ([1], [0], [0.0, 1.0]),
        ([0], [1], [1 / sqrt(2), 1 / sqrt(2)]),
        ([1], [1], [1 / sqrt(2), -1 / sqrt(2)]),
        ([1, 0], [0, 1], [0.0, 1 / sqrt(2), 0.0, 1 / sqrt(2)]),
    ],
)
def test_task62_oracle_matches_independent_bb84_and_qiskit_order(state, basis, expected):
    value = [[amplitude, 0.0] for amplitude in expected]
    result = _task62_bb84_value(state, basis, value)
    assert result["passed"] is True
    assert result["max_aligned_error"] < 1e-10
    phased = [[0.0, amplitude] for amplitude in expected]
    assert _task62_bb84_value(state, basis, phased)["passed"] is True


def test_task62_oracle_rejects_fixed_ignored_input_reversed_order_and_bad_shape():
    assert not _task62_bb84_value([1], [1], [[1 / sqrt(2), 0], [1 / sqrt(2), 0]])["passed"]
    assert not _task62_bb84_value([1, 0], [0, 0], [[0, 0], [0, 0], [1, 0], [0, 0]])["passed"]
    for value in ([], [[1, 0]], [[True, 0], [0, 0]], [[float("nan"), 0], [0, 0]]):
        assert _task62_bb84_value([0], [0], value)["passed"] is False
    assert _task62_bb84_value([0, 1], [0], [[1, 0], [0, 0]])["passed"] is False


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_case_set_cannot_be_reduced_or_replaced_with_bad_input():
    task = task62_value_task(source())
    with pytest.raises(ValidationError, match="task-62"):
        ProtectedSemanticTask(contract=task.contract, oracle=task.oracle, cases=task.cases[:-1])
    wrong = SemanticCase(case_id="bool-case", call=ValueCall(args=([True], [0])))
    with pytest.raises(ValidationError, match="task-62"):
        ProtectedSemanticTask(
            contract=task.contract, oracle=task.oracle, cases=(wrong, *task.cases[1:])
        )
    replacement = SemanticCase(
        case_id="width-5-state-00001-basis-00000",
        call=ValueCall(args=([0, 0, 0, 0, 1], [0, 0, 0, 0, 0])),
    )
    with pytest.raises(ValidationError, match="full frozen case set"):
        ProtectedSemanticTask(
            contract=task.contract, oracle=task.oracle, cases=(*task.cases[:-1], replacement)
        )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_judge_manifest_binds_contract_code_and_dispatches_all_cases():
    pinned = source()
    task = task62_value_task(pinned)

    class FakeRunner:
        def manifest(self, _contract):
            return {"runner": "test"}

        def execute(self, _contract, _completion, calls):
            values = tuple(
                [[1.0, 0.0]] + [[0.0, 0.0] for _ in range(2 ** len(call.args[0]) - 1)]
                for call in calls
            )
            return ValueExecution("returned", values, {"test": True})

    judge = ProtectedSemanticJudge(FakeRunner())
    manifest = judge.manifest(task)
    assert manifest["task62_contract_code_sha256"]
    result = judge.evaluate(task, pinned, "ignored by fake")
    assert result.outcome == "fail"
    assert len(result.evidence["case_results"]) == 124
    assert result.evidence["native_object_attested"] is False


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_authored_controls_cover_independent_and_wrong_styles():
    controls = protected_probes(source())
    assert len(controls) == len({probe.name for probe in controls}) == 8
    assert [probe.expectation for probe in controls] == [
        "pass",
        "pass",
        "pass",
        "fail",
        "fail",
        "fail",
        "fail",
        "fail",
    ]
    assert all("def bb84_sender_amplitudes(" in probe.completion for probe in controls)
    assert all(probe.rationale for probe in controls)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_control_runner_predeclares_selected_judge(monkeypatch, tmp_path):
    captured = {}

    def fake_run_review(sources, judge, output, *, probes_for, declared_judges):
        captured["sources"] = sources
        captured["declared"] = declared_judges
        captured["probes"] = probes_for(sources[0])

    monkeypatch.setattr("graybench.protected_oracle_review.run_review", fake_run_review)
    monkeypatch.setattr(
        "graybench.protected_oracle_review.inspect_oracle_review",
        lambda _path, _cache: {"control_count": 8},
    )
    report = run_protected_review(
        Path(CACHE),
        tmp_path / "controls.jsonl",
        suite="normal",
        image="sha256:" + "a" * 64,
        task_ids=("qiskitHumanEval/62",),
    )
    assert report == {"control_count": 8}
    assert [task.public.task_id for task in captured["sources"]] == ["qiskitHumanEval/62"]
    key = "normal/qiskitHumanEval/62"
    assert captured["declared"][key]["oracle"] == task62_value_task(source()).oracle
    assert len(captured["probes"]) == 8


def test_task62_cli_accepts_explicit_protected_control_selection(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_run(cache, output, *, suite, image, task_ids, docker, timeout):
        captured["task_ids"] = task_ids
        return {
            "file_sha256": "a" * 64,
            "control_count": 8,
            "controls_matching_expectation": 8,
            "task_keys": ["normal/qiskitHumanEval/62"],
        }

    monkeypatch.setattr("graybench.cli.run_protected_review", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "protected-oracle-review",
            str(tmp_path),
            str(tmp_path / "log.jsonl"),
            "--suite",
            "normal",
            "--image",
            "sha256:" + "a" * 64,
            "--task",
            "62",
        ],
    )
    main()
    assert captured["task_ids"] == ("qiskitHumanEval/62",)
    assert json.loads(capsys.readouterr().out)["control_count"] == 8


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task62_is_explicitly_plannable_without_admitting_other_tasks():
    pinned = source()
    task = task62_value_task(pinned)
    excluded = {
        f"normal/qiskitHumanEval/{number}": "unreviewed_or_unsupported"
        for number in range(151)
        if number != 62
    }
    cohort = freeze_protected_cohort(
        (task,),
        cache=Path(CACHE),
        suite="normal",
        image="sha256:" + "a" * 64,
        label="task62 value development",
        excluded=excluded,
    )
    model = ModelSpec(adapter="ollama", model="fixture", base_url="http://localhost:11434")
    setup = build_protected_setup("task62", model, cohort, (task,), cache=Path(CACHE))
    assert setup.protocol.task_keys == ("normal/qiskitHumanEval/62",)
    assert setup.protocol.protected_population == "custom_development"
    assert len(setup.cohort.excluded) == 150
    assert setup.purpose == "development"


@pytest.mark.skipif(not CACHE or not IMAGE, reason="Pinned cache and image required")
def test_task62_pinned_docker_judge_accepts_alternative_and_rejects_fixed_answer():
    pinned = source()
    task = task62_value_task(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=45))
    probes = {probe.name: probe for probe in protected_probes(pinned)}
    for name in ("qiskit-bb84", "global-phase-bb84", "fixed-zero-bb84"):
        probe = probes[name]
        verdict = judge.evaluate(task, pinned, probe.completion)
        assert verdict.outcome == probe.expectation, (name, verdict.evidence)
        assert len(verdict.evidence["case_results"]) == 124
        assert verdict.evidence["native_object_attested"] is False

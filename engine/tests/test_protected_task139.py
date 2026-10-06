"""Task 139's value revision checks Schmidt mathematics, not Qiskit object identity."""

import math
import os
from itertools import permutations
from pathlib import Path

import pytest
from pydantic import ValidationError

import graybench.protected_semantic_judge as semantic
from graybench.datasets import load_suite
from graybench.oracle_review import inspect_oracle_review
from graybench.protected_oracle_review import protected_probes
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_contract import ValueCall
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs/reliability-evidence/artifacts/task139-protected-controls-2026-10-06-v2/results.jsonl"
)


def source(suite="normal"):
    if not CACHE:
        pytest.skip("Pinned source cache required")
    return load_suite(suite, Path(CACHE))[139]


def state(*nonzero):
    amplitudes = [[0.0, 0.0] for _ in range(16)]
    for index, real, imaginary in nonzero:
        amplitudes[index] = [real, imaginary]
    return amplitudes


def basis(index, size=4):
    return [[1.0 if i == index else 0.0, 0.0] for i in range(size)]


def term(weight, a, b):
    return {"weight": weight, "a": a, "b": b}


def check(amplitudes, qargs_b, answer):
    return semantic._task139_schmidt_value(amplitudes, qargs_b, answer)


def test_schmidt_accepts_product_basis_with_sorted_subsystem_order():
    # qargs_B is intentionally unsorted. Qubit 2 is bit 1 of sorted B=[0,2].
    answer = [term(1.0, basis(0), basis(2))]
    assert check(state((4, 1, 0)), [2, 0], answer)["passed"] is True
    assert check(state((4, 1, 0)), [2, 0], [term(1, basis(0), basis(1))])["passed"] is False


def test_schmidt_accepts_reordered_phased_and_rotated_degenerate_terms():
    s = 1 / math.sqrt(2)
    target = state((0, s, 0), (5, s, 0))
    ordinary = [term(s, basis(0), basis(0)), term(s, basis(1), basis(1))]
    assert check(target, [0, 1], ordinary)["passed"] is True
    phased = [
        term(s, [[0, x[0]] for x in basis(1)], basis(1)),
        term(s, [[0, x[0]] for x in basis(0)], basis(0)),
    ]
    assert check(target, [0, 1], phased)["passed"] is True
    plus = [[s, 0], [s, 0], [0, 0], [0, 0]]
    minus = [[s, 0], [-s, 0], [0, 0], [0, 0]]
    rotated = [term(s, plus, plus), term(s, minus, minus)]
    assert check(target, [0, 1], rotated)["passed"] is True


def test_schmidt_rejects_empty_fixed_omitted_and_nonorthogonal_terms():
    s = 1 / math.sqrt(2)
    target = state((0, s, 0), (5, s, 0))
    wrong = (
        [],
        [term(1.0, basis(0), basis(0))],
        [term(s, basis(0), basis(0))],
        [term(s, basis(0), basis(0)), term(s, basis(0), basis(1))],
        [term(-s, basis(0), basis(0)), term(s, basis(1), basis(1))],
        [term(0.5, basis(0), basis(0)), term(0.5, basis(1), basis(1))],
    )
    assert all(check(target, [0, 1], answer)["passed"] is False for answer in wrong)


def test_schmidt_rejects_malformed_and_nonfinite_values_without_crashing():
    target = state((0, 1, 0))
    wrong = (
        [term(1, basis(0), basis(0)[:-1])],
        [term(True, basis(0), basis(0))],
        [term(float("nan"), basis(0), basis(0))],
        [term(1e308, basis(0), basis(0))],
        [term(10**400, basis(0), basis(0))],
        [term(1, [[float("inf"), 0]] + basis(0)[1:], basis(0))],
    )
    assert all(check(target, [0, 1], answer)["passed"] is False for answer in wrong)


def test_schmidt_case_roster_covers_all_ordered_partitions_and_six_states():
    cases = tuple(semantic.task139_case_inputs())
    assert len(cases) == 240
    partitions = [tuple(b) for _, b in cases]
    assert set(partitions) == {
        ordered for size in (1, 2, 3) for ordered in permutations(range(4), size)
    }
    assert all(partitions.count(partition) == 6 for partition in set(partitions))
    assert cases[0][0] == state((0, 1, 0))
    assert len({tuple(tuple(pair) for pair in amplitudes) for amplitudes, _ in cases}) == 6


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_schmidt_revision_binds_pinned_sources_and_rejects_case_mutation():
    from graybench.protected_task139 import TASK139_SOURCE_DIGESTS, task139_value_task

    for suite in ("normal", "hard"):
        pinned = source(suite)
        task = task139_value_task(pinned)
        assert pinned.digest == TASK139_SOURCE_DIGESTS[suite]
        assert task.contract.source_task_digest == pinned.digest
        assert task.contract.public.digest != pinned.public.digest
        assert task.contract.public.prompt_format == (
            "function_completion" if suite == "normal" else "standalone_function"
        )
        assert "sorted" in task.contract.public.prompt
        assert task.release_eligible is False
        assert len(task.cases) == 240
        assert revised_value_task(pinned) == task
        assert revised_value_task(pinned, oracle=task.oracle) == task
        with pytest.raises(ValueError, match="pinned QHE task-139"):
            task139_value_task(pinned.model_copy(update={"canonical_solution": "altered"}))
        for cases in (
            task.cases[:-1],
            (task.cases[1], task.cases[0], *task.cases[2:]),
            (
                task.cases[0].model_copy(update={"call": ValueCall(args=(state((0, 1, 0)), [1]))}),
                *task.cases[1:],
            ),
        ):
            with pytest.raises(ValidationError, match="full frozen case set"):
                semantic.ProtectedSemanticTask(
                    contract=task.contract, oracle=task.oracle, cases=cases
                )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_schmidt_controls_freeze_distinct_correct_and_wrong_answer_styles():
    for suite in ("normal", "hard"):
        probes = protected_probes(source(suite))
        assert [(probe.name, probe.expectation) for probe in probes] == [
            ("numpy-svd", "pass"),
            ("qiskit-schmidt", "pass"),
            ("global-phase", "pass"),
            ("reordered-terms", "pass"),
            ("degenerate-rotation", "pass"),
            ("empty-terms", "candidate_error"),
            ("fixed-zero", "fail"),
            ("omitted-term", "fail"),
            ("nonorthogonal", "fail"),
            ("bad-weight", "fail"),
            ("wrong-b-order", "fail"),
        ]
        assert all(probe.rationale for probe in probes)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_schmidt_control_log_binds_current_source_and_distinguishes_empty_answer():
    report = inspect_oracle_review(ARTIFACT, Path(CACHE))
    assert report["source_digest"] == source_manifest()["digest"]
    assert report["control_count"] == report["controls_matching_expectation"] == 22
    assert (report["expected_passes"], report["expected_failures"]) == (10, 10)
    assert report["expected_candidate_errors"] == 2
    assert not report["unexpected_outcomes"]
    assert report["independent_review"] is False
    assert report["publication_eligible"] is False


@pytest.mark.skipif(not CACHE or not IMAGE, reason="Pinned cache and image required")
def test_nonorthogonal_control_preserves_reconstruction_and_other_invariants():
    pinned = source()
    task = revised_value_task(pinned)
    generic = task.cases[5]
    assert generic.call.args[1] == [0]
    probe = next(p for p in protected_probes(pinned) if p.name == "nonorthogonal")
    execution = ValueRunner(image=IMAGE).execute(task.contract, probe.completion, (generic.call,))
    assert execution.outcome == "returned", execution.evidence
    answer = execution.values[0]
    assert len(answer) == 2

    def amplitudes(pairs):
        return [complex(real, imaginary) for real, imaginary in pairs]

    weights = [item["weight"] for item in answer]
    a = [amplitudes(item["a"]) for item in answer]
    b = [amplitudes(item["b"]) for item in answer]
    assert abs(sum(weight**2 for weight in weights) - 1) < 1e-8
    assert all(abs(sum(abs(z) ** 2 for z in vector) - 1) < 1e-8 for vector in (*a, *b))
    assert abs(sum(x.conjugate() * y for x, y in zip(b[0], b[1], strict=True))) < 1e-8
    assert abs(sum(x.conjugate() * y for x, y in zip(a[0], a[1], strict=True))) > 1e-3
    target = amplitudes(generic.call.args[0])
    actual = [
        sum(weights[k] * a[k][index >> 1] * b[k][index & 1] for k in range(2))
        for index in range(16)
    ]
    assert max(abs(x - y) for x, y in zip(target, actual, strict=True)) < 1e-8
    assert semantic._task139_schmidt_value(*generic.call.args, answer)["reason"] == (
        "nonorthogonal_a"
    )


@pytest.mark.skipif(not CACHE or not IMAGE, reason="Pinned cache and image required")
def test_schmidt_controls_run_in_isolated_worker_on_both_suites():
    judge = semantic.ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=90))
    for suite in ("normal", "hard"):
        pinned = source(suite)
        task = revised_value_task(pinned)
        assert "task139_contract_code_sha256" in judge.manifest(task)
        for probe in protected_probes(pinned):
            verdict = judge.evaluate(task, pinned, probe.completion)
            assert verdict.outcome == probe.expectation, (
                suite,
                probe.name,
                verdict.outcome,
                verdict.evidence,
            )

import ast
import hashlib

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from graybench.datasets import EXTERNAL_IDS, PINS, load_suite
from graybench.native_cohort import freeze_native_cohort, validate_native_cohort

IMAGE = "sha256:" + "a" * 64


@pytest.fixture
def cache(tmp_path, monkeypatch):
    for suite, marker in (("normal", "a"), ("hard", "b")):
        revision = marker * 40
        rows = [
            {
                "task_id": f"qiskitHumanEval/{number}",
                "prompt": (
                    'def answer():\n    """Return a number."""\n'
                    if suite == "normal"
                    else "Return a number with answer()."
                ),
                "entry_point": "answer",
                "test": (
                    f"def check(candidate):\n    assert candidate() == {number}\n"
                    + ("" if suite == "normal" else "check(answer)\n")
                ),
                "canonical_solution": (
                    f"    return {number}\n"
                    if suite == "normal"
                    else f"def answer():\n    return {number}\n"
                ),
                "difficulty_scale": "fixture",
            }
            for number in range(151)
        ]
        path = tmp_path / suite / revision[:12] / "data/test-00000-of-00001.parquet"
        path.parent.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist(rows), path)
        monkeypatch.setitem(
            PINS,
            suite,
            {
                "repo": f"fixture/{suite}",
                "revision": revision,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            },
        )
    return tmp_path


def selected(cache, suite, population="offline_143"):
    all_tasks = load_suite(suite, cache)
    if population == "offline_143":
        tasks = tuple(
            task
            for task in all_tasks
            if int(task.public.task_id.rsplit("/", 1)[1]) not in EXTERNAL_IDS
        )
        excluded = {
            f"{suite}/qiskitHumanEval/{number}": "external_service" for number in EXTERNAL_IDS
        }
    else:
        tasks = all_tasks[:2]
        excluded = {
            f"{suite}/qiskitHumanEval/{number}": "out_of_scope_development"
            for number in range(2, 151)
        }
    return tasks, excluded


def frozen(cache, suite="normal", population="offline_143"):
    tasks, excluded = selected(cache, suite, population)
    cohort = freeze_native_cohort(
        tasks,
        cache=cache,
        suite=suite,
        population=population,
        image=IMAGE,
        extraction="raw_or_single_python_fence_v1",
        label="fixture",
        excluded=excluded,
    )
    return cohort, tasks


def test_offline_cohort_binds_exact_source_and_stays_development_only(cache):
    cohort, tasks = frozen(cache)
    assert cohort.track == "qhe-pinned-native-v1"
    assert cohort.suite == "normal"
    assert cohort.population == "offline_143"
    assert len(cohort.task_keys) == 143
    assert len(cohort.excluded) == 8
    assert cohort.task_keys[0] == "normal/qiskitHumanEval/0"
    assert cohort.task_digests[cohort.task_keys[0]] == tasks[0].digest
    assert cohort.dataset_pin == PINS["normal"]
    assert cohort.image == IMAGE
    assert cohort.publication_eligible is False
    validate_native_cohort(cohort, tasks, cache=cache)


def test_normal_and_hard_have_distinct_frozen_identities(cache):
    normal, _ = frozen(cache, "normal")
    hard, _ = frozen(cache, "hard")
    assert normal.digest != hard.digest
    assert set(normal.task_keys).isdisjoint(hard.task_keys)


def test_exact_prompt_suffix_cohort_is_normal_only_and_separately_identified(cache):
    tasks, excluded = selected(cache, "normal")
    literal = freeze_native_cohort(
        tasks,
        cache=cache,
        suite="normal",
        population="offline_143",
        image=IMAGE,
        extraction="exact_prompt_suffix_v1",
        label="literal continuation",
        excluded=excluded,
    )
    chat, _ = frozen(cache, "normal")
    assert literal.digest != chat.digest
    assert literal.extraction == "exact_prompt_suffix_v1"
    hard_tasks, hard_excluded = selected(cache, "hard")
    with pytest.raises(ValueError, match="normal"):
        freeze_native_cohort(
            hard_tasks,
            cache=cache,
            suite="hard",
            population="offline_143",
            image=IMAGE,
            extraction="exact_prompt_suffix_v1",
            label="invalid hard continuation",
            excluded=hard_excluded,
        )


def test_mixed_or_duplicate_tasks_are_rejected(cache):
    tasks, excluded = selected(cache, "normal")
    hard = load_suite("hard", cache)[0]
    for invalid in (tasks + (hard,), tasks + (tasks[0],)):
        with pytest.raises(ValueError):
            freeze_native_cohort(
                invalid,
                cache=cache,
                suite="normal",
                population="offline_143",
                image=IMAGE,
                extraction="raw_or_single_python_fence_v1",
                label="fixture",
                excluded=excluded,
            )


def test_changed_task_bytes_are_rejected_at_freeze_and_resume(cache):
    cohort, tasks = frozen(cache)
    altered = (
        tasks[0].model_copy(update={"upstream_test": "def check(candidate): pass"}),
    ) + tasks[1:]
    with pytest.raises(ValueError):
        freeze_native_cohort(
            altered,
            cache=cache,
            suite="normal",
            population="offline_143",
            image=IMAGE,
            extraction="raw_or_single_python_fence_v1",
            label="fixture",
            excluded=cohort.excluded,
        )
    with pytest.raises(ValueError):
        validate_native_cohort(cohort, altered, cache=cache)


def test_mutated_manifest_or_pinned_file_is_rejected_on_resume(cache):
    cohort, tasks = frozen(cache)
    cohort.excluded.pop("normal/qiskitHumanEval/43")
    with pytest.raises(ValueError):
        validate_native_cohort(cohort, tasks, cache=cache)

    restored, tasks = frozen(cache)
    path = cache / "normal" / PINS["normal"]["revision"][:12] / "data/test-00000-of-00001.parquet"
    path.write_bytes(b"altered")
    with pytest.raises(ValueError):
        validate_native_cohort(restored, tasks, cache=cache)


def test_offline_population_rejects_missing_or_wrong_exclusion(cache):
    tasks, excluded = selected(cache, "normal")
    bad = dict(excluded)
    bad.pop("normal/qiskitHumanEval/43")
    for invalid in (bad, {**excluded, "normal/qiskitHumanEval/43": "unreviewed"}):
        with pytest.raises(ValueError):
            freeze_native_cohort(
                tasks,
                cache=cache,
                suite="normal",
                population="offline_143",
                image=IMAGE,
                extraction="raw_or_single_python_fence_v1",
                label="fixture",
                excluded=invalid,
            )


def test_custom_population_cannot_masquerade_as_offline_or_published(cache):
    custom, tasks = frozen(cache, population="custom_development")
    assert len(custom.task_keys) == 2
    assert custom.publication_eligible is False
    validate_native_cohort(custom, tasks, cache=cache)
    with pytest.raises(ValueError):
        freeze_native_cohort(
            tasks,
            cache=cache,
            suite="normal",
            population="offline_143",
            image=IMAGE,
            extraction="raw_or_single_python_fence_v1",
            label="151-task full score",
            excluded=custom.excluded,
        )


def test_all_pinned_tests_have_expected_top_level_check_shape(cache):
    for suite, expected in (("normal", 0), ("hard", 1)):
        for task in load_suite(suite, cache):
            top_level = [
                node
                for node in ast.parse(task.upstream_test).body
                if isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "check"
            ]
            assert len(top_level) == expected

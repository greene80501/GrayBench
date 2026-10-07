"""Task12 explicitly specifies the complete operator, not just one Bell column."""

import os
from pathlib import Path

import numpy as np
import pytest

from graybench.datasets import load_suite
from graybench.evaluation_recipes import recipe_judge
from graybench.task12_revision import CHECK, REQUIREMENT, TRACK

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:" + "a" * 64


def checker():
    scope = {}
    exec(compile(CHECK, "<authored-task12-check>", "exec"), scope)
    return scope["check"]


def controls_module():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task12_controls.py"
    spec = importlib.util.spec_from_file_location("task12_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authored(task, completion):
    code = task.public.prompt + completion if task.public.suite == "normal" else completion
    scope = {}
    exec(compile(code, "<authored-task12-control>", "exec"), scope)
    return scope[task.public.entry_point]


def literal_basis_operator():
    matrix = np.zeros((4, 4), dtype=complex)
    for column in range(4):
        q0, q1 = column & 1, column >> 1
        for out0 in range(2):
            row = ((q1 ^ out0) << 1) | out0
            matrix[row, column] = (-1) ** (q0 * out0) / np.sqrt(2)
    return matrix


@pytest.mark.parametrize("phase", [0.0, 0.37, -np.pi, np.pi / 2])
def test_complete_operator_and_declared_global_phase_pass(phase):
    value = np.exp(phase * 1j) * literal_basis_operator()
    checker()(lambda: value)


def test_correct_first_column_does_not_make_a_correct_operator():
    original = literal_basis_operator()
    values = [original @ np.diag([1, 1j, 1, 1]), original.copy(), np.eye(4, dtype=complex)]
    values[1][:, 1:] = 0
    for value in values:
        with pytest.raises(AssertionError, match="operator"):
            checker()(lambda value=value: value)


@pytest.mark.parametrize("change", ["nan", "inf", "huge", "scale", "shape", "list", "object"])
def test_invalid_values_fail_before_unsafe_phase_arithmetic(change):
    value = literal_basis_operator()
    if change in ("nan", "inf", "huge"):
        value[0, 0] = {"nan": np.nan, "inf": np.inf, "huge": 1e308 + 1e308j}[change]
    elif change == "scale":
        value *= 2
    elif change == "shape":
        value = value.reshape(2, 8)
    elif change == "list":
        value = value.tolist()
    else:
        value = value.astype(object)
    with np.errstate(all="raise"), pytest.raises(AssertionError):
        checker()(lambda: value)


def test_hostile_array_methods_are_not_called():
    class Forged:
        def __array__(self, *args, **kwargs):
            pytest.fail("A candidate method reached the checker")

    class Subclass(np.ndarray):
        def __array_ufunc__(self, *args, **kwargs):
            pytest.fail("A candidate ndarray subclass method reached the checker")

    for value in (Forged(), literal_basis_operator().view(Subclass)):
        with pytest.raises(AssertionError, match="plain NumPy"):
            checker()(lambda value=value: value)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_source_bound_revision_and_campaign_reconstruction(suite, model):
    from graybench.campaign_setup import CampaignSetup, build_setup
    from graybench.evaluation_campaign import validate_cohort

    source = load_suite(suite, Path(CACHE))[12]
    judge = recipe_judge(TRACK, image=IMAGE)
    revised = judge.revise(source)
    assert revised.digest != source.digest and judge.revise(revised) == revised
    assert revised.canonical_solution == source.canonical_solution
    assert revised.public.prompt_format == source.public.prompt_format
    assert REQUIREMENT in revised.public.prompt
    with pytest.raises(ValueError, match="Revise"):
        judge.configuration(source)
    for changed in (
        source.model_copy(update={"canonical_solution": "    return None"}),
        source.model_copy(update={"upstream_test": "def check(candidate): pass"}),
        source.model_copy(update={"public": source.public.model_copy(update={"prompt": "hint"})}),
        revised.model_copy(update={"upstream_test": "def check(candidate): pass"}),
    ):
        with pytest.raises(ValueError, match="exact pinned"):
            judge.revise(changed)
    payload, manifest = judge.configuration(revised)
    assert "graph_transport" not in payload
    assert manifest["inner"]["protocol"] == "upstream-proxy-v1"
    assert manifest["source_task_digest"] == source.digest
    assert manifest["public_contract_digest"] == revised.public.digest
    assert manifest["release_eligible"] is False
    setup = build_setup("explicit-bell-operator", model, (source,), IMAGE, evaluation_recipe=TRACK)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.output_limit == setup.output_limit
    tasks = restored.tasks(Path(CACHE))
    validate_cohort(restored.protocol, tasks, restored.judge())
    with pytest.raises((ValueError, RuntimeError)):
        validate_cohort(restored.protocol, (source,), restored.judge())


@pytest.mark.parametrize(
    "kwargs",
    [{"protocol": 4}, {"graph_transport": "delta-v1"}, {"graph_batch": "positional-batch-v1"}],
)
def test_recipe_cannot_silently_change_transport(kwargs):
    with pytest.raises(ValueError, match="requires"):
        recipe_judge(TRACK, image=IMAGE, **kwargs)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_all_authored_controls_through_actual_value_transport(suite):
    import json

    from graybench.value_wire import WireError, decode, encode

    source = load_suite(suite, Path(CACHE))[12]
    task = recipe_judge(TRACK, image=IMAGE).revise(source)
    probes = controls_module().probes(source)
    assert len(probes) == 29 and sum(p.expectation == "pass" for p in probes) == 15
    for probe in probes:
        implementation = authored(task, probe.completion)
        messages = []

        def proxy(implementation=implementation, messages=messages):
            request = {"kind": "call", "sequence": 1, "args": encode(()), "kwargs": encode({})}
            request = json.loads(json.dumps(request, allow_nan=False))
            result = implementation(*decode(request["args"]), **decode(request["kwargs"]))
            response = {
                "sequence": 1,
                "outcome": "returned",
                "response": {
                    "protocol": 3,
                    "value": encode(result),
                    "args_after": request["args"],
                    "kwargs_after": request["kwargs"],
                },
            }
            response = json.loads(json.dumps(response, allow_nan=False))
            messages.extend((request, response))
            returned = decode(response["response"]["value"])
            if type(result) is np.ndarray:
                assert returned.shape == result.shape and returned.dtype.str == result.dtype.str
                np.testing.assert_array_equal(returned, result)
            return returned

        if probe.expectation == "pass":
            checker()(proxy)
        elif probe.expectation == "unsupported":
            with pytest.raises(WireError):
                checker()(proxy)
            assert not messages
            continue
        else:
            with pytest.raises(AssertionError):
                checker()(proxy)
        assert len(messages) == 2
        assert (
            sum(len(json.dumps(m, allow_nan=False).encode()) for m in messages) + 8192 < 1024 * 1024
        )


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_isolated_controls_are_predeclared_before_execution(tmp_path, monkeypatch):
    import json
    import sys
    from collections import Counter

    module = controls_module()
    output = tmp_path / "controls.jsonl"

    class BeforeExecution(Exception):
        pass

    def stop(_judge, _task, _completion):
        header = json.loads(output.read_text().splitlines()[0])["event"]
        selection = header["selection"]
        assert Counter(case["expectation"] for case in selection["cases"].values()) == {
            "pass": 30,
            "fail": 26,
        }
        assert len(selection["declared_judges"]) == 2
        for manifest in selection["declared_judges"].values():
            assert manifest["track"] == TRACK and manifest["release_eligible"] is False
        raise BeforeExecution

    monkeypatch.setattr(module.ControlsJudge, "evaluate", stop)
    monkeypatch.setattr(
        sys,
        "argv",
        ["task12-controls", "--cache", CACHE, "--image", IMAGE, "--output", str(output)],
    )
    with pytest.raises(BeforeExecution):
        module.main()


@pytest.mark.parametrize("kind", ["subnormal", "signed-minimum"])
def test_extreme_invalid_pivot_is_a_semantic_failure(kind):
    value = literal_basis_operator()
    if kind == "subnormal":
        value[0, 0] = np.nextafter(0.0, 1.0)
    else:
        value = np.full((4, 4), np.iinfo(np.int64).min, dtype=np.int64)
    with np.errstate(all="raise"), pytest.raises(AssertionError):
        checker()(lambda: value)


def test_phase_alignment_does_not_privilege_one_matrix_entry():
    from graybench.value_wire import decode, encode

    original = literal_basis_operator()
    value = original @ np.diag(np.exp(1j * np.array([1.2e-10, -1.2e-10, 0, 0])))
    np.testing.assert_allclose(value.conj().T @ value, np.eye(4), atol=1e-15)
    assert np.max(np.abs(value - original)) < 1e-10
    checker()(lambda: decode(encode(value)))


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_every_provider_receives_only_revised_public_contract():
    import json

    from graybench.contracts import ModelSpec
    from graybench.providers import BUILTINS, adapter

    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[12]
        task = recipe_judge(TRACK, image=IMAGE).revise(source)
        for name in BUILTINS:
            model = ModelSpec(
                adapter=name,
                model="fixture-model",
                base_url="http://localhost:11434"
                if name == "ollama"
                else "https://example.test/v1",
            )
            provider = adapter(name)
            prepared = provider.prepare(model, task.public, None)
            encoded = json.dumps(prepared.body, ensure_ascii=False)
            assert json.dumps(task.public.prompt, ensure_ascii=False)[1:-1] in encoded
            assert json.dumps(task.upstream_test, ensure_ascii=False)[1:-1] not in encoded
            assert json.dumps(source.canonical_solution, ensure_ascii=False)[1:-1] not in encoded
            assert prepared.digest != provider.prepare(model, source.public, None).digest


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_TASK12_TEST_IMAGE"),
    reason="Explicit Task12 control image and pinned cache required",
)
def test_complete_isolated_semantic_roster_matches_declared_outcomes():
    module = controls_module()
    judge = module.ControlsJudge(image=os.environ["GRAYBENCH_TASK12_TEST_IMAGE"])
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[12]
        for probe in module.probes(source):
            if probe.expectation == "unsupported":
                continue  # Outside-domain codec screen, not an oracle verdict.
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

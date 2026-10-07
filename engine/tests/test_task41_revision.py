"""Explicit subsystem/phase contract, separate from contradictory pinned Task41."""

import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest
from qiskit.quantum_info import Operator

from graybench.datasets import load_suite
from graybench.evaluation_recipes import recipe_judge
from graybench.task41_revision import CHECK, REQUIREMENT, TRACK

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:" + "a" * 64


def checker():
    scope = {}
    exec(compile(CHECK, "<authored-task41-check>", "exec"), scope)
    return scope["check"]


def controls_module():
    path = Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task41_controls.py"
    spec = importlib.util.spec_from_file_location("task41_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tensor_operator():
    x = np.array([[0, 1], [1, 0]])
    y = np.array([[0, -1j], [1j, 0]])
    return Operator(np.kron(np.kron(y, np.eye(2)), x))


def test_full_operator_has_fixed_phase_and_explicit_subsystems():
    from graybench.value_wire import decode, encode

    value = tensor_operator()
    checker()(lambda: decode(encode(value)))
    for phase in (-1, 1j, np.exp(0.37j)):
        with pytest.raises(AssertionError, match="operator"):
            checker()(lambda phase=phase: phase * value)
    first_only = value.data.copy()
    first_only[:, 1:] = 0
    with pytest.raises(AssertionError, match="operator"):
        checker()(lambda: Operator(first_only))


@pytest.mark.parametrize("side", ["input", "output"])
def test_correct_matrix_with_wrong_subsystem_dimensions_fails(side):
    kwargs = {side + "_dims": (8,)}
    value = Operator(tensor_operator().data, **kwargs)
    with pytest.raises(AssertionError, match="dimensions"):
        checker()(lambda: value)


@pytest.mark.parametrize("change", ["nan", "inf", "huge", "shape", "list", "object"])
def test_invalid_operator_fails_without_numeric_exception(change):
    value = tensor_operator()
    if change in ("nan", "inf", "huge"):
        value.data[0, 0] = {"nan": np.nan, "inf": np.inf, "huge": 1e308 + 1e308j}[change]
    elif change == "shape":
        value = Operator(np.eye(4))
    elif change == "list":
        value = value.data.tolist()
    else:
        value._data = value.data.astype(object)
    with np.errstate(all="raise"), pytest.raises(AssertionError):
        checker()(lambda: value)


def test_hostile_equivalence_methods_are_not_called():
    class Forged:
        def __eq__(self, other):
            pytest.fail("Candidate equality reached the checker")

    class Subclass(Operator):
        def equiv(self, other):
            pytest.fail("Candidate equivalence reached the checker")

    for value in (Forged(), Subclass(tensor_operator().data)):
        with pytest.raises(AssertionError, match="plain"):
            checker()(lambda value=value: value)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_exact_source_revision_and_campaign_reconstruction(suite, model):
    from graybench.campaign_setup import CampaignSetup, build_setup
    from graybench.evaluation_campaign import validate_cohort

    source = load_suite(suite, Path(CACHE))[41]
    judge = recipe_judge(TRACK, image=IMAGE)
    task = judge.revise(source)
    assert task.digest != source.digest and judge.revise(task) == task
    assert task.canonical_solution == source.canonical_solution
    assert task.public.prompt_format == source.public.prompt_format
    assert REQUIREMENT in task.public.prompt
    with pytest.raises(ValueError, match="Revise"):
        judge.configuration(source)
    for changed in (
        source.model_copy(update={"canonical_solution": "return None"}),
        source.model_copy(update={"upstream_test": "def check(candidate): pass"}),
        source.model_copy(update={"public": source.public.model_copy(update={"prompt": "hint"})}),
        task.model_copy(update={"upstream_test": "def check(candidate): pass"}),
    ):
        with pytest.raises(ValueError, match="exact pinned"):
            judge.revise(changed)
    payload, manifest = judge.configuration(task)
    assert "graph_transport" not in payload
    assert manifest["inner"]["protocol"] == "upstream-proxy-v1"
    assert manifest["source_task_digest"] == source.digest
    assert manifest["public_contract_digest"] == task.public.digest
    assert manifest["release_eligible"] is False
    setup = build_setup(
        "explicit-pauli-subsystems", model, (source,), IMAGE, evaluation_recipe=TRACK
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    validate_cohort(restored.protocol, restored.tasks(Path(CACHE)), restored.judge())
    with pytest.raises((ValueError, RuntimeError)):
        validate_cohort(restored.protocol, (source,), restored.judge())


@pytest.mark.parametrize(
    "kwargs", [{"protocol": 4}, {"graph_transport": "delta-v1"}, {"graph_limits": "implicit"}]
)
def test_recipe_cannot_silently_change_transport(kwargs):
    with pytest.raises(ValueError, match="requires"):
        recipe_judge(TRACK, image=IMAGE, **kwargs)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_provider_requests_use_only_revised_public_contract():
    import json

    from graybench.contracts import ModelSpec
    from graybench.providers import BUILTINS, adapter

    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[41]
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
            request = provider.prepare(model, task.public, None)
            body = json.dumps(request.body, ensure_ascii=False)
            assert json.dumps(task.public.prompt, ensure_ascii=False)[1:-1] in body
            assert json.dumps(task.upstream_test, ensure_ascii=False)[1:-1] not in body
            assert json.dumps(source.canonical_solution, ensure_ascii=False)[1:-1] not in body
            assert request.digest != provider.prepare(model, source.public, None).digest


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_complete_authored_roster_through_production_value_codec(suite):
    import json
    from collections import Counter

    from graybench.value_wire import WireError, decode, encode

    source = load_suite(suite, Path(CACHE))[41]
    task = recipe_judge(TRACK, image=IMAGE).revise(source)
    probes = controls_module().probes(source)
    assert Counter(p.expectation for p in probes) == {"pass": 18, "fail": 25, "unsupported": 2}
    for probe in probes:
        program = task.public.prompt + probe.completion if suite == "normal" else probe.completion
        scope = {}
        exec(compile(program, "<authored-task41-control>", "exec"), scope)
        implementation = scope[task.public.entry_point]
        messages = []

        def proxy(implementation=implementation, messages=messages):
            request = {"kind": "call", "sequence": 1, "args": encode(()), "kwargs": encode({})}
            request = json.loads(json.dumps(request, allow_nan=False))
            result = implementation(*decode(request["args"]), **decode(request["kwargs"]))
            wire = {
                "protocol": 3,
                "sequence": 1,
                "value": encode(result),
                "args_after": request["args"],
                "kwargs_after": request["kwargs"],
            }
            response = {"sequence": 1, "outcome": "returned", "response": wire}
            response = json.loads(json.dumps(response, allow_nan=False))
            messages.extend((request, response))
            returned = decode(response["response"]["value"])
            if type(result) is Operator:
                assert returned.input_dims() == result.input_dims()
                assert returned.output_dims() == result.output_dims()
                np.testing.assert_array_equal(returned.data, result.data)
            return returned

        if probe.expectation == "pass":
            checker()(proxy)
        elif probe.expectation == "unsupported":
            with pytest.raises(WireError):
                checker()(proxy)
            assert not messages
            continue
        else:
            with np.errstate(all="raise"), pytest.raises(AssertionError):
                checker()(proxy)
        assert len(messages) == 2
        assert (
            sum(len(json.dumps(m, allow_nan=False).encode()) for m in messages) + 8192 < 1024 * 1024
        )


def test_binding_metadata_is_explicitly_unattested():
    from graybench.value_wire import decode, encode

    bound = tensor_operator()([2, 1, 0])
    assert bound.qargs == (2, 1, 0)
    result = decode(encode(bound))
    assert result.qargs is None
    checker()(lambda: result)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_isolated_semantic_roster_predeclared_before_execution(tmp_path, monkeypatch):
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
            "pass": 36,
            "fail": 50,
        }
        assert len(selection["declared_judges"]) == 2
        for manifest in selection["declared_judges"].values():
            assert manifest["track"] == TRACK and manifest["release_eligible"] is False
        raise BeforeExecution

    monkeypatch.setattr(module.ControlsJudge, "evaluate", stop)
    monkeypatch.setattr(
        sys,
        "argv",
        ["task41-controls", "--cache", CACHE, "--image", IMAGE, "--output", str(output)],
    )
    with pytest.raises(BeforeExecution):
        module.main()


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_TASK41_TEST_IMAGE"),
    reason="Explicit Task41 control image and pinned cache required",
)
def test_complete_isolated_semantic_roster_matches_declared_outcomes():
    module = controls_module()
    judge = module.ControlsJudge(image=os.environ["GRAYBENCH_TASK41_TEST_IMAGE"])
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[41]
        for probe in module.semantic_probes(source):
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

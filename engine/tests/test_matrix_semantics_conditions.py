"""Input-sensitive matrix conditions must bind source, semantics and resources."""

import os
from pathlib import Path

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.datasets import load_suite
from graybench.evaluation_campaign import validate_cohort
from graybench.evaluation_recipes import recipe_judge

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:" + "a" * 64
RECIPES = {
    116: "qhe116-evolution-graph-v2",
    120: "qhe120-diagonal-graph-v2",
    125: "qhe125-gate-action-graph-v1",
}


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("number", RECIPES)
def test_matrix_plan_reconstructs_exact_task_and_resources_before_generation(number, model):
    sources = tuple(load_suite(suite, Path(CACHE))[number] for suite in ("normal", "hard"))
    setup = build_setup(
        "matrix-development", model, sources, IMAGE, evaluation_recipe=RECIPES[number]
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.output_limit == 16 * 1024 * 1024
    tasks = restored.tasks(Path(CACHE))
    validate_cohort(restored.protocol, tasks, restored.judge())
    for source, task in zip(sources, tasks, strict=True):
        assert source.digest != task.digest
        assert task.canonical_solution == source.canonical_solution
        assert task.public.prompt_format == source.public.prompt_format
        payload, manifest = restored.judge().configuration(task)
        assert payload["graph_transport"]["mode"] == "delta-v1"
        assert payload["graph_limits"]["depth"] == 128
        assert manifest["source_task_digest"] == source.digest
        assert manifest["public_contract_digest"] == task.public.digest
        assert manifest["release_eligible"] is False


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("number", RECIPES)
def test_matrix_condition_refuses_a_reused_task_identity_with_changed_source(number):
    source = load_suite("normal", Path(CACHE))[number]
    judge = recipe_judge(RECIPES[number], image=IMAGE)
    for modified in (
        source.model_copy(update={"upstream_test": "def check(candidate): pass"}),
        source.model_copy(update={"canonical_solution": "    return None"}),
        source.model_copy(
            update={"public": source.public.model_copy(update={"prompt": "Help me"})}
        ),
    ):
        with pytest.raises(ValueError, match="exact pinned"):
            judge.revise(modified)
    with pytest.raises(ValueError, match="Revise"):
        judge.configuration(source)


def controls_module(filename="matrix_semantics_controls.py"):
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "docs/reliability-evidence" / filename
    spec = importlib.util.spec_from_file_location("matrix_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checker(task):
    namespace = {}
    exec(compile(task.upstream_test, "<authored-matrix-checker>", "exec"), namespace)
    return namespace["check"]


def authored(task, completion):
    code = task.public.prompt + completion if task.public.suite == "normal" else completion
    namespace = {}
    exec(compile(code, "<authored-matrix-control>", "exec"), namespace)
    return namespace[task.public.entry_point]


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("number", RECIPES)
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_authored_alternatives_and_wrong_actions_match_the_public_contract(number, suite):
    pytest.importorskip("qiskit")
    source = load_suite(suite, Path(CACHE))[number]
    task = recipe_judge(RECIPES[number], image=IMAGE).revise(source)
    for probe in controls_module().probes(source):
        implementation = authored(task, probe.completion)
        if probe.expectation == "pass":
            checker(task)(implementation)
        else:
            with pytest.raises(AssertionError):
                checker(task)(implementation)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize(
    "number,name",
    [
        (116, "canonical"),
        (116, "parity-rotations"),
        (120, "parity-phases"),
        (120, "canonical"),
        (120, "consume-input"),
        (125, "unitary-gate"),
        (125, "canonical"),
        (125, "mutate-input"),
        (125, "nested"),
    ],
)
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_full_retained_graph_roundtrip_preserves_alternatives_and_input_mutation(
    number, name, suite
):
    pytest.importorskip("qiskit")
    import json

    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_delta import DeltaGraphArena
    from graybench.graph_limits import GraphLimits
    from graybench.graph_rpc import validate_root_shapes
    from graybench.graph_wire import GraphArena

    source = load_suite(suite, Path(CACHE))[number]
    judge = recipe_judge(RECIPES[number], image=IMAGE)
    task = judge.revise(source)
    probe = next(p for p in controls_module().probes(source) if p.name == name)
    implementation = authored(task, probe.completion)
    payload, _ = judge.configuration(task)
    limits = GraphLimits.from_record(payload["graph_limits"])
    if number == 116 and name == "canonical":
        observed = controls_module("canonical_evolution_transport.py").probe_case(
            implementation, "I", 0.0, limits
        )
        if observed["graph_outcome"] == "unsupported":
            assert observed["numerical_outcome"] == "pass"
            assert observed["owner_chain"][-1]["type"] == "PySliceContainer"
            if os.environ.get("GRAYBENCH_REQUIRE_CANONICAL_GRAPH") == "1":
                pytest.fail("Actual canonical evolution graph transport is unsupported")
            pytest.skip("Observed unsupported canonical PySliceContainer graph storage")
    anchors = PublicAnchorRegistry.capture()
    sender = DeltaGraphArena(
        GraphArena(side="judge", session="matrix", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    receiver = DeltaGraphArena(
        GraphArena(side="candidate", session="matrix", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    calls, request_bytes, response_bytes, first_nodes = 0, 0, 0, set()

    def proxy(*args):
        nonlocal calls, request_bytes, response_bytes, first_nodes
        calls += 1
        request = sender.snapshot({"args": args, "kwargs": {}}, sequence=calls)
        request_bytes += len(json.dumps(request, allow_nan=False).encode())
        incoming = receiver.commit(receiver.prepare(request, sequence=calls))
        result = implementation(*incoming["args"])
        response = receiver.snapshot(
            {**incoming, "result": result, "exception_args": None}, sequence=calls
        )
        response_bytes += len(json.dumps(response, allow_nan=False).encode())
        prepared = sender.prepare(response, sequence=calls)
        validate_root_shapes(prepared.snapshot, response=True, raised=None)
        nodes = {node["id"] for node in prepared.snapshot["nodes"]}
        if calls == 1:
            first_nodes = nodes
        assert first_nodes <= nodes
        return sender.commit(prepared)["result"]

    checker(task)(proxy)
    assert calls == {116: 16, 120: 12, 125: 18}[number]
    assert request_bytes + 8192 < limits.message_bytes
    assert response_bytes + 8192 < limits.message_bytes


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("number,passes,failures", [(116, 6, 12), (120, 10, 14), (125, 10, 22)])
def test_cli_reserves_all_controls_and_bound_judges_before_execution(
    number, passes, failures, tmp_path, monkeypatch
):
    import json
    import sys
    from collections import Counter

    module = controls_module()
    output = tmp_path / "matrix-controls.jsonl"

    class BeforeExecution(Exception):
        pass

    def stop(_judge, _task, _completion):
        header = json.loads(output.read_text().splitlines()[0])["event"]
        selection = header["selection"]
        assert Counter(case["expectation"] for case in selection["cases"].values()) == {
            "pass": passes,
            "fail": failures,
        }
        declared = selection["declared_judges"]
        assert len(declared) == 2
        for manifest in declared.values():
            assert manifest["track"] == RECIPES[number]
            assert manifest["inner"]["graph_limits"]["depth"] == 128
            assert manifest["runtime_qualification"].startswith("unqualified")
        raise BeforeExecution

    monkeypatch.setattr(module.MatrixControlsJudge, "evaluate", stop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "matrix-controls",
            "--cache",
            CACHE,
            "--image",
            IMAGE,
            "--evaluation-recipe",
            RECIPES[number],
            "--output",
            str(output),
        ],
    )
    with pytest.raises(BeforeExecution):
        module.main()


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("number", RECIPES)
def test_all_builtin_adapters_prepare_only_the_revised_public_contract(number):
    import json

    from graybench.contracts import ModelSpec
    from graybench.providers import BUILTINS, adapter

    judge = recipe_judge(RECIPES[number], image=IMAGE)
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[number]
        task = judge.revise(source)
        for name in BUILTINS:
            model = ModelSpec(
                adapter=name,
                model="probe-model",
                base_url=(
                    "http://localhost:11434" if name == "ollama" else "https://example.test/v1"
                ),
            )
            provider = adapter(name)
            request = provider.prepare(model, task.public, None)
            encoded = json.dumps(request.body, ensure_ascii=False)
            assert json.dumps(task.public.prompt, ensure_ascii=False)[1:-1] in encoded
            assert json.dumps(task.upstream_test, ensure_ascii=False)[1:-1] not in encoded
            assert json.dumps(source.canonical_solution, ensure_ascii=False)[1:-1] not in encoded
            assert request.digest != provider.prepare(model, source.public, None).digest


@pytest.mark.parametrize("recipe", RECIPES.values())
@pytest.mark.parametrize(
    "kwargs",
    [
        {"protocol": 3},
        {"graph_transport": "snapshot-v1"},
        {"graph_batch": "bb84-v1"},
    ],
)
def test_matrix_conditions_cannot_silently_change_transport(recipe, kwargs):
    with pytest.raises(ValueError, match="requires"):
        recipe_judge(recipe, image=IMAGE, **kwargs)


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_MATRIX_TEST_IMAGE"),
    reason="Explicitly qualified matrix runtime image and cache required",
)
@pytest.mark.parametrize("number", RECIPES)
def test_isolated_matrix_controls_all_match_declared_outcomes(number):
    module = controls_module()
    judge = module.MatrixControlsJudge(
        RECIPES[number], image=os.environ["GRAYBENCH_MATRIX_TEST_IMAGE"]
    )
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[number]
        for probe in module.probes(source):
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

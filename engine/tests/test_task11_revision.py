"""Task 11 must score the original input action, not a saved example state."""

import os
from pathlib import Path

import pytest

from graybench.datasets import KNOWN_FINDINGS, KNOWN_FINDINGS_V2, load_suite
from graybench.evaluation_recipes import recipe_judge

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:" + "a" * 64
TRACK = "qhe11-statevector-action-graph-v1"


def controls_module():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task11_controls.py"
    assert path.is_file(), "Task 11 needs a predeclared positive/negative control roster"
    spec = importlib.util.spec_from_file_location("task11_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checker(task):
    scope = {}
    exec(compile(task.upstream_test, "<authored-task11-check>", "exec"), scope)
    return scope


def authored(task, completion):
    code = task.public.prompt + completion if task.public.suite == "normal" else completion
    scope = {}
    exec(compile(code, "<authored-task11-control>", "exec"), scope)
    return scope[task.public.entry_point]


def test_fixed_input_finding_is_current_only():
    assert 11 not in KNOWN_FINDINGS_V2
    assert 11 in KNOWN_FINDINGS
    assert "input-independent" in " ".join(KNOWN_FINDINGS[11])


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_source_bound_revision_is_opt_in_and_refuses_changed_sources(suite):
    source = load_suite(suite, Path(CACHE))[11]
    judge = recipe_judge(TRACK, image=IMAGE)
    revised = judge.revise(source)
    assert revised.digest != source.digest
    assert judge.revise(revised) == revised
    assert revised.canonical_solution == source.canonical_solution
    assert revised.public.prompt_format == source.public.prompt_format
    with pytest.raises(ValueError, match="Revise"):
        judge.configuration(source)
    for changed in (
        source.model_copy(update={"upstream_test": "def check(candidate): pass"}),
        source.model_copy(update={"canonical_solution": "    return None"}),
        source.model_copy(update={"public": source.public.model_copy(update={"prompt": "hint"})}),
    ):
        with pytest.raises(ValueError, match="exact pinned"):
            judge.revise(changed)
    payload, manifest = judge.configuration(revised)
    assert payload["graph_transport"]["mode"] == "delta-v1"
    assert manifest["source_task_digest"] == source.digest
    assert manifest["public_contract_digest"] == revised.public.digest
    assert manifest["release_eligible"] is False


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_all_correct_alternatives_pass_and_wrong_values_fail(suite):
    source = load_suite(suite, Path(CACHE))[11]
    revised = recipe_judge(TRACK, image=IMAGE).revise(source)
    probes = controls_module().probes(source)
    assert len(probes) == 16
    assert sum(p.expectation == "pass" for p in probes) == 5
    for probe in probes:
        implementation = authored(revised, probe.completion)
        if probe.expectation == "pass":
            checker(revised)["check"](implementation)
        else:
            with pytest.raises(AssertionError):
                checker(revised)["check"](implementation)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_expected_states_are_independent_and_case_roster_has_43_inputs():
    import numpy as np
    from qiskit.quantum_info import Statevector

    source = load_suite("normal", Path(CACHE))[11]
    revised = recipe_judge(TRACK, image=IMAGE).revise(source)
    cases = checker(revised)["statevector_cases"]()
    assert len(cases) == 43
    assert {circuit.num_qubits for circuit, _ in cases} == set(range(1, 6))
    for circuit, expected in cases:
        assert np.allclose(
            Statevector.from_instruction(circuit).data, expected[:, 0], atol=1e-14, rtol=0
        )


@pytest.mark.parametrize(
    "kwargs", [{"protocol": 3}, {"graph_transport": "snapshot-v1"}, {"graph_batch": "bb84-v1"}]
)
def test_task11_cannot_change_its_graph_transport(kwargs):
    with pytest.raises(ValueError, match="requires"):
        recipe_judge(TRACK, image=IMAGE, **kwargs)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_campaign_reconstructs_the_same_declared_resource_condition(model):
    from graybench.campaign_setup import CampaignSetup, build_setup
    from graybench.evaluation_campaign import validate_cohort

    sources = tuple(load_suite(suite, Path(CACHE))[11] for suite in ("normal", "hard"))
    setup = build_setup("state-action-development", model, sources, IMAGE, evaluation_recipe=TRACK)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.output_limit == 16 * 1024 * 1024
    tasks = restored.tasks(Path(CACHE))
    validate_cohort(restored.protocol, tasks, restored.judge())
    small = recipe_judge(TRACK, image=IMAGE, output_limit=8 * 1024 * 1024)
    assert small.configuration(tasks[0])[1] != restored.judge().configuration(tasks[0])[1]
    with pytest.raises(ValueError):
        validate_cohort(restored.protocol, tasks, small)


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
@pytest.mark.parametrize(
    "name", ["canonical", "operator-column", "indexed-simulator", "global-phase", "consume-input"]
)
def test_full_retained_graph_preserves_correct_state_values_and_permitted_mutation(suite, name):
    import json

    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_delta import DeltaGraphArena
    from graybench.graph_limits import GraphLimits
    from graybench.graph_rpc import validate_root_shapes
    from graybench.graph_wire import GraphArena

    source = load_suite(suite, Path(CACHE))[11]
    judge = recipe_judge(TRACK, image=IMAGE)
    task = judge.revise(source)
    probe = next(p for p in controls_module().probes(source) if p.name == name)
    implementation = authored(task, probe.completion)
    payload, _ = judge.configuration(task)
    limits = GraphLimits.from_record(payload["graph_limits"])
    anchors = PublicAnchorRegistry.capture()
    sender = DeltaGraphArena(
        GraphArena(side="judge", session="state-action", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    receiver = DeltaGraphArena(
        GraphArena(side="candidate", session="state-action", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    calls, request_bytes, response_bytes, first_nodes = 0, 0, 0, set()

    def proxy(circuit):
        nonlocal calls, request_bytes, response_bytes, first_nodes
        calls += 1
        request = sender.snapshot({"args": (circuit,), "kwargs": {}}, sequence=calls)
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

    checker(task)["check"](proxy)
    assert calls == 43
    assert request_bytes + 8192 < limits.message_bytes
    assert response_bytes + 8192 < limits.message_bytes


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_controls_are_reserved_before_any_execution(tmp_path, monkeypatch):
    import json
    import sys
    from collections import Counter

    module = controls_module()
    output = tmp_path / "controls.jsonl"

    class BeforeExecution(Exception):
        pass

    def stop(_judge, _task, _completion):
        header = json.loads(output.read_text(encoding="utf-8").splitlines()[0])["event"]
        selection = header["selection"]
        assert Counter(case["expectation"] for case in selection["cases"].values()) == {
            "pass": 10,
            "fail": 22,
        }
        assert len(selection["declared_judges"]) == 2
        for manifest in selection["declared_judges"].values():
            assert manifest["track"] == TRACK
            assert manifest["runtime_qualification"].startswith("unqualified")
            assert manifest["inner"]["graph_limits"]["depth"] == 128
        raise BeforeExecution

    monkeypatch.setattr(module.ControlsJudge, "evaluate", stop)
    monkeypatch.setattr(
        sys,
        "argv",
        ["task11-controls", "--cache", CACHE, "--image", IMAGE, "--output", str(output)],
    )
    with pytest.raises(BeforeExecution):
        module.main()


@pytest.mark.skipif(not CACHE, reason="Needs pinned QHE source")
def test_all_builtin_adapters_receive_contract_but_no_private_tests():
    import json

    from graybench.contracts import ModelSpec
    from graybench.providers import BUILTINS, adapter

    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[11]
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
    not CACHE or not os.environ.get("GRAYBENCH_STATEVECTOR_TEST_IMAGE"),
    reason="Explicitly qualified statevector image and pinned cache required",
)
def test_complete_isolated_control_roster_matches_declared_outcomes():
    module = controls_module()
    judge = module.ControlsJudge(image=os.environ["GRAYBENCH_STATEVECTOR_TEST_IMAGE"])
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[11]
        for probe in module.probes(source):
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

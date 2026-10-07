"""Declared circuit nesting needs a separately frozen graph resource condition."""

import os
from pathlib import Path

import pytest
from test_task117_protected_graph import candidate, checker, controls_module

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.datasets import load_suite
from graybench.evaluation_campaign import cohort_identities, validate_cohort
from graybench.evaluation_recipes import recipe_judge
from graybench.graph_limits import GraphLimits

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
V1 = "qhe117-unitary-basis-graph-v1"
V2 = "qhe117-unitary-basis-graph-v2"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_nested_resource_condition_is_distinct_and_reconstructs_without_changing_task(model):
    sources = tuple(load_suite(suite, Path(CACHE))[117] for suite in ("normal", "hard"))
    legacy = build_setup("legacy-unitary", model, sources, IMAGE, evaluation_recipe=V1)
    setup = build_setup("nested-unitary", model, sources, IMAGE, evaluation_recipe=V2)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.output_limit == 16 * 1024 * 1024
    old_tasks, tasks = legacy.tasks(Path(CACHE)), restored.tasks(Path(CACHE))
    assert [t.digest for t in old_tasks] == [t.digest for t in tasks]
    assert legacy.protocol.request_digests == setup.protocol.request_digests
    assert legacy.protocol.judge_digest != setup.protocol.judge_digest
    validate_cohort(restored.protocol, tasks, restored.judge())
    payload, manifest = restored.judge().configuration(tasks[0])
    old_payload, old_manifest = legacy.judge().configuration(old_tasks[0])
    assert payload["graph_limits"]["depth"] == manifest["inner"]["graph_limits"]["depth"] == 128
    assert old_payload["graph_limits"]["depth"] == 32
    assert manifest["track"] == V2 and old_manifest["track"] == V1
    for field in ("array_bytes", "matrix_bytes"):
        assert payload["graph_limits"][field] == old_payload["graph_limits"][field] == 524288


def test_depth_extension_does_not_change_the_legacy_default():
    assert GraphLimits().depth == 32
    extended = GraphLimits(depth=128)
    assert GraphLimits.from_record(extended.record()) == extended


@pytest.mark.parametrize("value", [True, 0, -1, 129, 1.5])
def test_extended_depth_remains_strictly_bounded(value):
    from graybench.circuit_wire import WireError

    with pytest.raises(WireError, match="resource"):
        GraphLimits(depth=value)


def test_legacy_condition_cannot_silently_select_the_new_depth():
    with pytest.raises(ValueError, match="historical graph depth"):
        recipe_judge(V1, image=IMAGE, graph_limits=GraphLimits(depth=128))


@pytest.mark.parametrize("depth", [32, 127])
def test_nested_condition_rejects_an_unmatched_resource_record(depth):
    with pytest.raises(ValueError, match="frozen graph resource"):
        recipe_judge(
            V2,
            image=IMAGE,
            graph_limits=GraphLimits(message_bytes=16 * 1024 * 1024, depth=depth),
        )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("suite", ["normal", "hard"])
@pytest.mark.parametrize("levels", range(16))
def test_complete_corpus_traverses_both_graph_arenas_at_every_declared_circuit_depth(suite, levels):
    pytest.importorskip("qiskit")
    import json

    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_delta import DeltaGraphArena
    from graybench.graph_rpc import validate_root_shapes
    from graybench.graph_wire import GraphArena
    from graybench.task117_revision import revised_task

    source = load_suite(suite, Path(CACHE))[117]
    task = revised_task(source)
    probe = next(
        p for p in controls_module().nested_probes(source) if p.name == f"definition-depth-{levels}"
    )
    authored = candidate(task, probe.completion)
    payload, _ = recipe_judge(V2, image=IMAGE).configuration(task)
    limits = GraphLimits.from_record(payload["graph_limits"])
    anchors = PublicAnchorRegistry.capture()
    sender = DeltaGraphArena(
        GraphArena(side="judge", session="task117-depth", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    receiver = DeltaGraphArena(
        GraphArena(side="candidate", session="task117-depth", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    calls, sent_bytes, returned_bytes, first_nodes = 0, 0, 0, set()

    def proxy(unitary):
        nonlocal calls, sent_bytes, returned_bytes, first_nodes
        calls += 1
        request = sender.snapshot({"args": (unitary,), "kwargs": {}}, sequence=calls)
        sent_bytes += len(json.dumps(request, allow_nan=False).encode())
        incoming = receiver.commit(receiver.prepare(request, sequence=calls))
        result = authored(*incoming["args"])
        response = receiver.snapshot(
            {**incoming, "result": result, "exception_args": None}, sequence=calls
        )
        returned_bytes += len(json.dumps(response, allow_nan=False).encode())
        prepared = sender.prepare(response, sequence=calls)
        validate_root_shapes(prepared.snapshot, response=True, raised=None)
        nodes = {n["id"] for n in prepared.snapshot["nodes"]}
        if calls == 1:
            first_nodes = nodes
        assert first_nodes <= nodes
        return sender.commit(prepared)["result"]

    checker(task)(proxy)
    assert calls == 15
    assert sent_bytes + 8192 < limits.message_bytes
    assert returned_bytes + 8192 < limits.message_bytes


def test_extended_sender_cannot_override_the_receivers_historical_depth():
    from graybench.circuit_wire import WireLimitError
    from graybench.graph_wire import GraphArena

    value = []
    for _ in range(40):
        value = [value]
    sender = GraphArena(side="judge", session="limits", limits=GraphLimits(depth=128))
    receiver = GraphArena(side="candidate", session="limits", limits=GraphLimits())
    wire = sender.snapshot({"value": value}, sequence=1)
    with pytest.raises(WireLimitError, match="nesting"):
        receiver.prepare(wire, sequence=1)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_explicit_byte_budget_cannot_execute_or_compare_as_the_default_condition(model):
    from graybench.comparison import make_plan
    from graybench.ledger import StateError

    sources = tuple(load_suite(suite, Path(CACHE))[117] for suite in ("normal", "hard"))
    setup = build_setup("nested-default", model, sources, IMAGE, evaluation_recipe=V2)
    tasks = setup.tasks(Path(CACHE))
    smaller = recipe_judge(V2, image=IMAGE, output_limit=1024 * 1024)
    payload, manifest = smaller.configuration(tasks[0])
    assert payload["graph_limits"]["message_bytes"] == 1024 * 1024
    assert manifest["inner"]["graph_limits"]["depth"] == 128
    with pytest.raises(StateError, match="Frozen cohort mismatch: judge_digest"):
        validate_cohort(setup.protocol, tasks, smaller)
    bound = cohort_identities(tasks, smaller)
    protocol = setup.protocol.model_copy(update={"judge_digest": bound["judge_digest"]})
    assert protocol.digest != setup.protocol.digest
    validate_cohort(protocol, tasks, smaller)
    with pytest.raises(StateError, match="Comparison protocols differ in judge_digest"):
        make_plan(
            setup.protocol,
            protocol,
            tasks,
            seed=19,
            configuration_comparison="Different explicitly selected byte allowances",
        )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_v2_cli_reserves_full_control_roster_and_judge_before_execution(tmp_path, monkeypatch):
    import json
    import sys
    from collections import Counter

    module = controls_module()
    output = tmp_path / "nested-controls.jsonl"

    class BeforeExecution(Exception):
        pass

    def stop(_judge, _task, _completion):
        header = json.loads(output.read_text().splitlines()[0])["event"]
        selection = header["selection"]
        cases = selection["cases"]
        assert len(cases) == 80
        assert Counter(case["expectation"] for case in cases.values()) == {"pass": 50, "fail": 30}
        assert {key for key in cases if "/definition-depth-" in key} == {
            f"{suite}/qiskitHumanEval/117/definition-depth-{level}"
            for suite in ("normal", "hard")
            for level in range(16)
        }
        declared = selection["declared_judges"]
        assert len(declared) == 2
        for manifest in declared.values():
            assert manifest["track"] == V2
            assert manifest["inner"]["graph_limits"]["depth"] == 128
        raise BeforeExecution

    monkeypatch.setattr(module.Task117GraphJudge, "evaluate", stop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "task117-controls",
            "--cache",
            CACHE,
            "--image",
            IMAGE,
            "--evaluation-recipe",
            V2,
            "--output",
            str(output),
        ],
    )
    with pytest.raises(BeforeExecution):
        module.main()


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_TEST_IMAGE"),
    reason="Pinned image and cache required",
)
def test_isolated_v2_controls_match_predeclared_outcomes():
    module = controls_module()
    judge = module.Task117GraphJudge(image=os.environ["GRAYBENCH_TEST_IMAGE"], track=V2)
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[117]
        for probe in module.nested_probes(source):
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

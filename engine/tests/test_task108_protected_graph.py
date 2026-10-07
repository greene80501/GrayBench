"""All-return-value Choi checks and a frozen, separately selected condition."""

import importlib.util
import os
from pathlib import Path

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.datasets import load_suite
from graybench.evaluation_campaign import validate_cohort
from graybench.providers import Ollama

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
RECIPE = "qhe108-choi-values-graph-v1"


def controls_module():
    path = (
        Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task108_protected_graph.py"
    )
    spec = importlib.util.spec_from_file_location("task108_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate(task, completion):
    namespace = {}
    code = task.public.prompt + completion if task.public.suite == "normal" else completion
    exec(compile(code, "<authored-task108-control>", "exec"), namespace)
    return namespace[task.public.entry_point]


def checker(task):
    namespace = {}
    exec(compile(task.upstream_test, "<authored-task108-oracle>", "exec"), namespace)
    return namespace["check"]


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task108_plan_freezes_all_value_condition_before_generation(model):
    sources = tuple(load_suite(suite, Path(CACHE))[108] for suite in ("normal", "hard"))
    setup = build_setup("choi-development", model, sources, IMAGE, evaluation_recipe=RECIPE)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.output_limit == 16 * 1024 * 1024
    tasks = restored.tasks(Path(CACHE))
    validate_cohort(restored.protocol, tasks, restored.judge())
    payload, _ = restored.judge().configuration(tasks[0])
    assert payload["graph_limits"]["array_bytes"] == 4 * 1024 * 1024
    assert payload["graph_transport"]["mode"] == "delta-v1"
    for source, task in zip(sources, tasks, strict=True):
        assert task.public.prompt_format == source.public.prompt_format
        assert task.public.family_id == source.public.family_id
        assert task.canonical_solution == source.canonical_solution
        key = f"{task.public.suite}/{task.public.task_id}"
        assert (
            setup.protocol.request_digests[key] == Ollama().prepare(model, task.public, None).digest
        )
        assert (
            setup.protocol.request_digests[key]
            != Ollama().prepare(model, source.public, None).digest
        )
        assert task.upstream_test != source.upstream_test
        assert "1e-8" in task.public.prompt
        assert "adjoint" in task.public.prompt


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task108_all_returns_oracle_rejects_wrong_values_and_accepts_equivalent_constructions():
    pytest.importorskip("qiskit")
    from graybench.task108_revision import revised_task

    source = load_suite("normal", Path(CACHE))[108]
    task = revised_task(source)
    namespace = {}
    exec(compile(task.upstream_test, "<authored-task108-oracle>", "exec"), namespace)
    from qiskit.quantum_info import Choi, SuperOp

    def direct(a, b):
        first, second = Choi(a), Choi(b)
        return first, first.adjoint(), first.compose(second)

    # A different representation and explicit matrix product, not an oracle helper.
    def via_superop(a, b):
        first, second = SuperOp(Choi(a)), SuperOp(Choi(b))
        return (
            Choi(first),
            Choi(SuperOp(first.data.conj().T)),
            Choi(SuperOp(second.data @ first.data)),
        )

    namespace["check"](direct)
    namespace["check"](via_superop)
    for wrong in (
        lambda a, b: (Choi(a * 0), direct(a, b)[1], direct(a, b)[2]),
        lambda a, b: (Choi(a), direct(a, b)[1], Choi(a)),
        lambda a, b: (Choi(a), Choi(a.conj().T), direct(a, b)[2]),
        lambda a, b: (Choi(a), direct(a, b)[1], Choi(b).compose(Choi(a))),
    ):
        with pytest.raises(AssertionError):
            namespace["check"](wrong)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_predeclared_authored_controls_match_both_public_formats():
    pytest.importorskip("qiskit")
    from graybench.task108_revision import revised_task

    module = controls_module()
    outcomes = []
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[108]
        task = revised_task(source)
        for probe in module.probes(source):
            try:
                checker(task)(candidate(task, probe.completion))
            except AssertionError:
                outcome = "fail"
            else:
                outcome = "pass"
            assert outcome == probe.expectation, (suite, probe.name)
            outcomes.append(outcome)
    assert outcomes.count("pass") == 8
    assert outcomes.count("fail") == 20


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize(
    "name", ["direct", "superop-product", "mutate-inputs", "ignore-data2", "zero-first"]
)
def test_choi_graph_roundtrip_keeps_complete_values_and_mutated_input_contract(name):
    pytest.importorskip("qiskit")
    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_delta import DeltaGraphArena
    from graybench.graph_rpc import validate_root_shapes
    from graybench.graph_wire import GraphArena, GraphLimits
    from graybench.task108_revision import ChoiValuesJudge, revised_task

    source = load_suite("normal", Path(CACHE))[108]
    task = revised_task(source)
    probe = next(probe for probe in controls_module().probes(source) if probe.name == name)
    authored = candidate(task, probe.completion)
    anchors = PublicAnchorRegistry.capture()
    payload, _ = ChoiValuesJudge(image=IMAGE).configuration(task)
    limits = GraphLimits.from_record(payload["graph_limits"])
    sender = DeltaGraphArena(
        GraphArena(side="judge", session="task108", anchors=anchors, limits=limits),
        wire_limit=limits.message_bytes,
    )
    receiver = DeltaGraphArena(
        GraphArena(side="candidate", session="task108", anchors=anchors, limits=limits),
        wire_limit=limits.message_bytes,
    )
    calls, widths = 0, set()
    sent_bytes, returned_bytes, first_nodes = 0, 0, set()

    def proxy(first, second):
        nonlocal calls, sent_bytes, returned_bytes, first_nodes
        import json

        calls += 1
        widths.add(first.shape[0])
        outgoing = sender.snapshot({"args": (first, second), "kwargs": {}}, sequence=calls)
        sent_bytes += len(json.dumps(outgoing, allow_nan=False).encode())
        incoming = receiver.commit(receiver.prepare(outgoing, sequence=calls))
        result = authored(*incoming["args"])
        returned = receiver.snapshot(
            {**incoming, "result": result, "exception_args": None}, sequence=calls
        )
        returned_bytes += len(json.dumps(returned, allow_nan=False).encode())
        prepared = sender.prepare(returned, sequence=calls)
        validate_root_shapes(prepared.snapshot, response=True, raised=None)
        nodes = {node["id"] for node in prepared.snapshot["nodes"]}
        if calls == 1:
            first_nodes = nodes
        assert first_nodes <= nodes
        for key in ("args", "kwargs"):
            assert returned["roots"][key] == outgoing["roots"][key]
        return sender.commit(prepared)["result"]

    if probe.expectation == "pass":
        checker(task)(proxy)
        assert calls == 19
        assert widths == {4, 16, 64}
        assert sent_bytes + 8192 < limits.message_bytes
        assert returned_bytes + 8192 < limits.message_bytes
    else:
        with pytest.raises(AssertionError):
            checker(task)(proxy)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("field", ["upstream_test", "canonical_solution"])
def test_changed_source_or_revised_checker_cannot_reuse_condition(field):
    from graybench.task108_revision import revised_task

    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[108]
        revised = revised_task(source)
        assert revised_task(revised).digest == revised.digest
        for task in (source, revised):
            with pytest.raises(ValueError, match="exact pinned QHE task-108"):
                revised_task(task.model_copy(update={field: "changed"}))


@pytest.mark.parametrize(
    "options", [{"protocol": 3}, {"graph_transport": "snapshot-v1"}, {"graph_batch": "enabled"}]
)
def test_choi_condition_rejects_other_transport_conditions(options):
    from graybench.task108_revision import ChoiValuesJudge

    with pytest.raises(ValueError, match="requires"):
        ChoiValuesJudge(image=IMAGE, **options)


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_TEST_IMAGE"),
    reason="Pinned image and cache required",
)
def test_isolated_choi_controls_match_predeclared_outcomes():
    module = controls_module()
    judge = module.Task108GraphJudge(image=os.environ["GRAYBENCH_TEST_IMAGE"])
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[108]
        for probe in module.probes(source):
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

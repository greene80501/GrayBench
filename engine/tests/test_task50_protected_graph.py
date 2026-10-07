"""Position-sensitive circuit editing, without prescribing copy versus mutation."""

import importlib.util
import os
from pathlib import Path

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.datasets import load_suite
from graybench.evaluation_campaign import validate_cohort
from graybench.identity import identity
from graybench.providers import Ollama

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "docs/reliability-evidence/task50_protected_graph.py"
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")


def revision():
    assert MODULE.is_file(), "Position-sensitive task-50 revision is missing"
    spec = importlib.util.spec_from_file_location("task50_protected_graph", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task50_requires_exact_pinned_source_and_preserves_information_conditions():
    module = revision()
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[50]
        task = module.revised_task(source)
        assert task.public.prompt_format == source.public.prompt_format
        assert task.public.family_id == source.public.family_id
        assert task.public.digest != source.public.digest
        assert task.digest != source.digest
        assert task.canonical_solution == source.canonical_solution
        with pytest.raises(ValueError, match="exact pinned QHE task-50"):
            module.revised_task(source.model_copy(update={"upstream_test": "changed"}))


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_campaign_recipe_freezes_the_revised_request_before_generation(model):
    module = revision()
    sources = tuple(load_suite(suite, Path(CACHE))[50] for suite in ("normal", "hard"))
    setup = build_setup(
        "task50-development",
        model,
        sources,
        module.IMAGE,
        evaluation_recipe="qhe50-remove-position-graph-v1",
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    revised = restored.tasks(Path(CACHE))
    validate_cohort(restored.protocol, revised, restored.judge())
    for source, task in zip(sources, revised, strict=True):
        key = f"{task.public.suite}/{task.public.task_id}"
        assert (
            setup.protocol.request_digests[key] == Ollama().prepare(model, task.public, None).digest
        )
        assert (
            setup.protocol.request_digests[key]
            != Ollama().prepare(model, source.public, None).digest
        )
        assert task.public.digest == module.revised_task(source).public.digest
    with pytest.raises(ValueError, match="exact pinned QHE task-50"):
        setup.judge().revise(sources[0].model_copy(update={"canonical_solution": "changed"}))


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_authored_controls_accept_mutation_and_copies_and_reject_semantic_errors():
    pytest.importorskip("qiskit")
    module = revision()
    outcomes = []
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[50]
        task = module.revised_task(source)
        for control in module.probes(source):
            namespace = {}
            code = (
                task.public.prompt + control.completion if suite == "normal" else control.completion
            )
            exec(compile(code, "<authored-task50-control>", "exec"), namespace)
            exec(compile(task.upstream_test, "<task50-development-oracle>", "exec"), namespace)
            try:
                namespace["check"](namespace[task.public.entry_point])
            except AssertionError:
                observed = "fail"
            else:
                observed = "pass"
            assert observed == control.expectation, (suite, control.name, observed)
            outcomes.append((suite, control.name, observed))
    assert len(outcomes) >= 20
    assert {name for _, name, outcome in outcomes if outcome == "pass"} >= {
        "in-place",
        "copy-delete",
        "rebuild",
    }


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("in_place", [False, True])
def test_graph_roundtrip_preserves_circuit_edit_for_all_authored_inputs(in_place):
    pytest.importorskip("qiskit")
    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_rpc import validate_root_shapes
    from graybench.graph_wire import GraphArena, GraphLimits

    module = revision()
    source = load_suite("normal", Path(CACHE))[50]
    task = module.revised_task(source)
    namespace = {}
    exec(compile(task.upstream_test, "<task50-development-oracle>", "exec"), namespace)
    anchors = PublicAnchorRegistry.capture()
    sender = GraphArena(side="judge", session="task50", anchors=anchors, limits=GraphLimits())
    receiver = GraphArena(side="candidate", session="task50", anchors=anchors, limits=GraphLimits())
    calls = 0

    def proxy(circuit, position):
        nonlocal calls
        calls += 1
        outgoing = sender.snapshot({"args": (circuit, position), "kwargs": {}}, sequence=calls)
        incoming = receiver.commit(receiver.prepare(outgoing, sequence=calls))
        remote = incoming["args"][0]
        result = remote if in_place else remote.copy()
        del result.data[position]
        returned = receiver.snapshot(
            {**incoming, "result": result, "exception_args": None}, sequence=calls
        )
        validate_root_shapes(returned, response=True, raised=None)
        for key in ("args", "kwargs"):
            assert returned["roots"][key] == outgoing["roots"][key]
        reconstructed = sender.commit(sender.prepare(returned, sequence=calls))
        if in_place:
            assert reconstructed["result"] is circuit
        return reconstructed["result"]

    namespace["check"](proxy)
    assert calls >= 20


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_editing_oracle_rejects_tiny_parameter_changes_without_sdk_tolerance():
    pytest.importorskip("qiskit")
    module = revision()
    source = load_suite("normal", Path(CACHE))[50]
    task = module.revised_task(source)
    namespace = {}
    exec(compile(task.upstream_test, "<task50-development-oracle>", "exec"), namespace)

    def nudge(circuit, position):
        result = circuit.copy()
        del result.data[position]
        for index, item in enumerate(result.data):
            if item.operation.name == "rx":
                operation = item.operation.to_mutable()
                operation.params[0] += 1e-12
                result.data[index] = item.replace(operation=operation)
        return result

    with pytest.raises(AssertionError, match="ordered instructions"):
        namespace["check"](nudge)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("graph", [False, True])
@pytest.mark.parametrize("mutation", ["register-family", "operation-name", "operation-definition"])
def test_preserved_circuit_components_cannot_change_after_removal(graph, mutation):
    qiskit = pytest.importorskip("qiskit")
    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_wire import GraphArena, GraphLimits

    module = revision()
    task = module.revised_task(load_suite("normal", Path(CACHE))[50])
    namespace = {}
    exec(compile(task.upstream_test, "<task50-development-oracle>", "exec"), namespace)

    def wrong(circuit, position):
        if mutation == "register-family":
            result = qiskit.QuantumCircuit(
                *(qiskit.circuit.AncillaRegister(len(r), r.name) for r in circuit.qregs),
                *(qiskit.ClassicalRegister(len(r), r.name) for r in circuit.cregs),
                global_phase=circuit.global_phase,
            )
            for index, item in enumerate(circuit.data):
                if index != position:
                    result.append(
                        item.operation,
                        [result.qubits[circuit.find_bit(q).index] for q in item.qubits],
                        [result.clbits[circuit.find_bit(c).index] for c in item.clbits],
                    )
            return result
        result = circuit.copy()
        del result.data[position]
        for index, item in enumerate(result.data):
            if item.operation.name == "rx":
                operation = item.operation.to_mutable()
                if mutation == "operation-name":
                    operation.name = "bogus"
                else:
                    definition = qiskit.QuantumCircuit(1)
                    definition.x(0)
                    operation.definition = definition
                result.data[index] = item.replace(operation=operation)
        return result

    anchors = PublicAnchorRegistry.capture()
    judge = GraphArena(side="judge", session="task50", anchors=anchors, limits=GraphLimits())
    candidate = GraphArena(
        side="candidate", session="task50", anchors=anchors, limits=GraphLimits()
    )
    calls = 0

    def proxy(circuit, position):
        nonlocal calls
        calls += 1
        incoming = candidate.commit(
            candidate.prepare(
                judge.snapshot({"args": (circuit, position), "kwargs": {}}, sequence=calls),
                sequence=calls,
            )
        )
        result = wrong(*incoming["args"])
        returned = candidate.snapshot(
            {**incoming, "result": result, "exception_args": None},
            sequence=calls,
        )
        return judge.commit(judge.prepare(returned, sequence=calls))["result"]

    with pytest.raises(AssertionError):
        namespace["check"](proxy if graph else wrong)


@pytest.mark.skipif(not CACHE or not IMAGE, reason="Pinned cache and Docker image required")
def test_isolated_graph_controls_match_their_predeclared_outcomes():
    module = revision()
    judge = module.Task50GraphJudge(image=IMAGE)
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[50]
        _, manifest = judge.configuration(source)
        for control in module.probes(source):
            result = judge.evaluate(source, control.completion)
            assert result.outcome == control.expectation, (suite, control.name, result.evidence)
            assert result.judge_digest == identity(manifest)

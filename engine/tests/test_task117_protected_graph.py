"""Input-sensitive two-qubit synthesis checks; authored fixtures only on the host."""

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
RECIPE = "qhe117-unitary-basis-graph-v1"


def checker(task):
    namespace = {}
    exec(compile(task.upstream_test, "<authored-task117-oracle>", "exec"), namespace)
    return namespace["check"]


def controls_module():
    path = (
        Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task117_protected_graph.py"
    )
    spec = importlib.util.spec_from_file_location("task117_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate(task, completion):
    namespace = {}
    code = task.public.prompt + completion if task.public.suite == "normal" else completion
    exec(compile(code, "<authored-task117-control>", "exec"), namespace)
    return namespace[task.public.entry_point]


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_plan_binds_revised_public_contract_and_reconstructs_same_judge(model):
    sources = tuple(load_suite(suite, Path(CACHE))[117] for suite in ("normal", "hard"))
    setup = build_setup("unitary-development", model, sources, IMAGE, evaluation_recipe=RECIPE)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.output_limit == 16 * 1024 * 1024
    tasks = restored.tasks(Path(CACHE))
    validate_cohort(restored.protocol, tasks, restored.judge())
    payload, _ = restored.judge().configuration(tasks[0])
    assert payload["graph_transport"]["mode"] == "delta-v1"
    for source, task in zip(sources, tasks, strict=True):
        assert task.public.prompt_format == source.public.prompt_format
        assert task.canonical_solution == source.canonical_solution
        key = f"{task.public.suite}/{task.public.task_id}"
        assert (
            setup.protocol.request_digests[key] == Ollama().prepare(model, task.public, None).digest
        )
        assert (
            setup.protocol.request_digests[key]
            != Ollama().prepare(model, source.public, None).digest
        )
        assert "global phase" in task.public.prompt
        assert "1e-8" in task.public.prompt


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_oracle_accepts_equivalent_outputs_and_rejects_input_independent_or_nonunitary_returns():
    pytest.importorskip("qiskit")
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import CXGate
    from qiskit.synthesis import TwoQubitBasisDecomposer

    from graybench.task117_revision import revised_task

    task = revised_task(load_suite("normal", Path(CACHE))[117])
    decompose = TwoQubitBasisDecomposer(CXGate())
    checker(task)(decompose)

    def other_basis(unitary):
        qc = QuantumCircuit(2)
        qc.unitary(unitary, [0, 1])
        return transpile(qc, basis_gates=["rz", "sx", "cx"], optimization_level=0)

    def nested(unitary):
        qc = QuantumCircuit(2, 1)
        qc.append(decompose(unitary).to_gate(), [0, 1])
        qc.barrier()
        qc.global_phase += 0.63
        return qc

    checker(task)(other_basis)
    checker(task)(nested)
    for wrong in (
        lambda unitary: QuantumCircuit(2),
        lambda unitary: QuantumCircuit(3),
    ):
        with pytest.raises(AssertionError):
            checker(task)(wrong)

    def constant_cx(unitary):
        qc = QuantumCircuit(2)
        qc.cx(0, 1)
        return qc

    def measured(unitary):
        qc = QuantumCircuit(2, 1)
        qc.cx(0, 1)
        qc.measure(0, 0)
        return qc

    for wrong in (constant_cx, measured):
        with pytest.raises(AssertionError):
            checker(task)(wrong)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_judge_does_not_synthesize_an_opaque_matrix_instruction_for_the_candidate():
    pytest.importorskip("qiskit")
    from qiskit import QuantumCircuit

    from graybench.task117_revision import revised_task

    task = revised_task(load_suite("normal", Path(CACHE))[117])

    def opaque(unitary):
        qc = QuantumCircuit(2)
        qc.unitary(unitary, [0, 1])
        return qc

    with pytest.raises(AssertionError, match="explicit composite"):
        checker(task)(opaque)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_open_control_cx_is_evaluated_with_its_actual_control_state():
    pytest.importorskip("qiskit")
    from qiskit.circuit.library import CXGate
    from qiskit.quantum_info import Operator
    from qiskit.synthesis import TwoQubitBasisDecomposer

    from graybench.task117_revision import revised_task

    task = revised_task(load_suite("normal", Path(CACHE))[117])
    decompose = TwoQubitBasisDecomposer(CXGate())

    def changed_controls(unitary, compensate=False):
        source = decompose(unitary)
        output = source.copy_empty_like()
        for item in source.data:
            wires = tuple(source.find_bit(q).index for q in item.qubits)
            if isinstance(item.operation, CXGate):
                if compensate:
                    output.x(wires[0])
                output.append(CXGate(ctrl_state=0), wires)
                if compensate:
                    output.x(wires[0])
            else:
                output.append(item.operation, wires)
        return output

    assert not Operator(changed_controls(Operator(CXGate()))).equiv(Operator(CXGate()))
    with pytest.raises(AssertionError, match="supplied unitary"):
        checker(task)(changed_controls)
    checker(task)(lambda u: changed_controls(u, compensate=True))


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("violation", ["timing", "depth"])
def test_local_composite_definitions_obey_the_same_leaf_and_depth_contract(violation):
    pytest.importorskip("qiskit")
    from qiskit import QuantumCircuit
    from qiskit.circuit import Gate
    from qiskit.circuit.library import CXGate
    from qiskit.synthesis import TwoQubitBasisDecomposer

    from graybench.task117_revision import revised_task

    task = revised_task(load_suite("normal", Path(CACHE))[117])

    def wrong(unitary):
        result = TwoQubitBasisDecomposer(CXGate())(unitary)
        local = QuantumCircuit(1)
        if violation == "timing":
            local.delay(123, 0, unit="dt")
        else:
            for index in range(18):
                gate = Gate(f"nested{index}", 1, [])
                gate.definition = local
                local = QuantumCircuit(1)
                local.append(gate, [0])
        gate = Gate("explicit-local", 1, [])
        gate.definition = local
        result.append(gate, [0])
        return result

    with pytest.raises(AssertionError, match="unitary gates|depth"):
        checker(task)(wrong)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("field", ["upstream_test", "canonical_solution"])
def test_changed_source_or_revised_checker_cannot_reuse_condition(field):
    from graybench.task117_revision import revised_task

    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[117]
        revised = revised_task(source)
        assert revised_task(revised).digest == revised.digest
        for task in (source, revised):
            with pytest.raises(ValueError, match="exact pinned QHE task-117"):
                revised_task(task.model_copy(update={field: "changed"}))


@pytest.mark.parametrize(
    "options", [{"protocol": 3}, {"graph_transport": "snapshot-v1"}, {"graph_batch": "enabled"}]
)
def test_condition_rejects_unsupported_transport(options):
    from graybench.task117_revision import UnitaryBasisJudge

    with pytest.raises(ValueError, match="requires"):
        UnitaryBasisJudge(image=IMAGE, **options)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_predeclared_controls_match_both_public_formats():
    pytest.importorskip("qiskit")
    from graybench.task117_revision import revised_task

    outcomes = []
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[117]
        task = revised_task(source)
        for probe in controls_module().probes(source):
            try:
                checker(task)(candidate(task, probe.completion))
            except AssertionError:
                outcome = "fail"
            else:
                outcome = "pass"
            assert outcome == probe.expectation, (suite, probe.name)
            outcomes.append(outcome)
    assert outcomes.count("pass") == 18
    assert outcomes.count("fail") == 30


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_independent_qr_alternative_matches_actual_operator_on_additional_inputs():
    pytest.importorskip("qiskit")
    import itertools

    import numpy as np
    from qiskit.quantum_info import Operator

    from graybench.task117_revision import revised_task

    source = load_suite("normal", Path(CACHE))[117]
    task = revised_task(source)
    probe = next(p for p in controls_module().probes(source) if p.name == "qr-givens")
    authored = candidate(task, probe.completion)
    rng = np.random.default_rng(251)
    inputs = [np.eye(4)[:, order] for order in itertools.permutations(range(4))]
    inputs.extend(np.diag(np.exp(1j * rng.uniform(-np.pi, np.pi, 4))) for _ in range(20))
    inputs.extend(
        np.linalg.qr(rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4)))[0] for _ in range(100)
    )
    assert len(inputs) == 144
    for matrix in inputs:
        actual = np.asarray(Operator(authored(Operator(matrix.copy()))).data)
        # Stronger than the development contract: this fixture retains global phase too.
        assert np.allclose(actual, matrix, atol=5e-12, rtol=0)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize(
    "name",
    [
        "direct",
        "qr-givens",
        "zyz-basis",
        "transpile-basis",
        "nested-phase",
        "mutate-input",
        "open-control-equivalent",
        "local-composite",
        "constant-cx",
        "opaque-matrix",
        "changed-control-state",
        "nested-timing",
    ],
)
def test_complete_graph_roundtrip_preserves_input_semantics_and_retained_nodes(name):
    pytest.importorskip("qiskit")
    import json

    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_delta import DeltaGraphArena
    from graybench.graph_rpc import validate_root_shapes
    from graybench.graph_wire import GraphArena, GraphLimits
    from graybench.task117_revision import UnitaryBasisJudge, revised_task

    source = load_suite("normal", Path(CACHE))[117]
    task = revised_task(source)
    probe = next(p for p in controls_module().probes(source) if p.name == name)
    authored = candidate(task, probe.completion)
    anchors = PublicAnchorRegistry.capture()
    payload, _ = UnitaryBasisJudge(image=IMAGE).configuration(task)
    limits = GraphLimits.from_record(payload["graph_limits"])
    sender = DeltaGraphArena(
        GraphArena(side="judge", session="task117", anchors=anchors, limits=limits),
        wire_limit=limits.message_bytes,
    )
    receiver = DeltaGraphArena(
        GraphArena(side="candidate", session="task117", anchors=anchors, limits=limits),
        wire_limit=limits.message_bytes,
    )
    calls, sent_bytes, returned_bytes, first_nodes = 0, 0, 0, set()

    def proxy(unitary):
        nonlocal calls, sent_bytes, returned_bytes, first_nodes
        calls += 1
        outgoing = sender.snapshot({"args": (unitary,), "kwargs": {}}, sequence=calls)
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
        assert returned["roots"]["args"] == outgoing["roots"]["args"]
        return sender.commit(prepared)["result"]

    if probe.expectation == "pass":
        checker(task)(proxy)
        assert calls == 15
        assert sent_bytes + 8192 < limits.message_bytes
        assert returned_bytes + 8192 < limits.message_bytes
    else:
        with pytest.raises(AssertionError):
            checker(task)(proxy)


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_TEST_IMAGE"),
    reason="Pinned image and cache required",
)
def test_isolated_controls_match_predeclared_outcomes():
    module = controls_module()
    judge = module.Task117GraphJudge(image=os.environ["GRAYBENCH_TEST_IMAGE"])
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[117]
        for probe in module.probes(source):
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

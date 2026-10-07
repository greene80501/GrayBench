import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Gate, Instruction

from graybench.datasets import load_suite
from graybench.evaluation_recipes import recipe_judge

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:" + "a" * 64


def revision():
    from graybench import task66_revision

    return task66_revision


def checker():
    scope = {}
    exec(compile(revision().CHECK, "<authored-task66-check>", "exec"), scope)
    return scope["check"]


def evidence_module(name, monkeypatch):
    import sys

    directory = Path(__file__).resolve().parents[2] / "docs/reliability-evidence"
    if name == "task66_state_verification":
        controls = evidence_module("task66_state_controls", monkeypatch)
        monkeypatch.setitem(sys.modules, "task66_state_controls", controls)
    spec = importlib.util.spec_from_file_location(name, directory / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preparation():
    circuit = QuantumCircuit(3)
    vector = np.zeros(8, dtype=complex)
    vector[[1, 2, 4]] = 1 / np.sqrt(3)
    circuit.prepare_state(vector)
    return circuit


def measured(circuit):
    circuit.measure_all()
    return circuit


def test_symmetric_density_matrix_rejects_relative_phase_and_accepts_global_phase():
    for phase in (0, 0.37, -1.2, np.pi):
        circuit = preparation()
        circuit.global_phase = phase
        checker()(lambda circuit=circuit: measured(circuit))
    for wire in range(3):
        circuit = preparation()
        circuit.z(wire)
        with pytest.raises(AssertionError, match="W state"):
            checker()(lambda circuit=circuit: measured(circuit))


def test_resets_and_initialize_are_allowed_before_final_measurements():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.reset(range(3))
    vector = np.zeros(8, dtype=complex)
    vector[[1, 2, 4]] = 1 / np.sqrt(3)
    circuit.initialize(vector)
    checker()(lambda: measured(circuit))


def test_measurement_order_mapping_and_unused_classical_bits_are_not_hidden_constraints():
    import itertools

    for wires in itertools.permutations(range(3)):
        circuit = QuantumCircuit(3, 7)
        circuit.compose(preparation(), inplace=True)
        for wire, classical in zip(wires, (6, 1, 4), strict=True):
            circuit.measure(wire, classical)
            circuit.barrier()
        checker()(lambda circuit=circuit: circuit)


@pytest.mark.parametrize("packaging", ["gate", "instruction", "nested-measurements"])
def test_explicit_composite_definitions_preserve_state_and_measurement_mapping(packaging):
    body = preparation()
    if packaging == "gate":
        wrapped = Gate("authored", 3, [])
    elif packaging == "instruction":
        wrapped = Instruction("authored", 3, 0, [])
    else:
        body = measured(body)
        wrapped = Instruction("authored", 3, 3, [])
    wrapped.definition = body
    circuit = QuantumCircuit(3, 3 if packaging == "nested-measurements" else 0)
    circuit.append(wrapped, [2, 0, 1], [1, 2, 0] if packaging == "nested-measurements" else [])
    if packaging != "nested-measurements":
        measured(circuit)
    checker()(lambda: circuit)


@pytest.mark.parametrize(
    "change", ["missing", "duplicate-qubit", "shared-bit", "gate-after", "reset-after", "early"]
)
def test_measurement_contract_is_checked_separately_from_final_probabilities(change):
    circuit = QuantumCircuit(3, 3)
    circuit.compose(preparation(), inplace=True)
    if change == "early":
        circuit.measure(0, 0)
        circuit.z(0)
        circuit.z(0)
        circuit.measure(1, 1)
        circuit.measure(2, 2)
    else:
        circuit.measure(0, 0)
        circuit.measure(1, 0 if change == "shared-bit" else 1)
        if change != "missing":
            circuit.measure(0 if change == "duplicate-qubit" else 2, 2)
        if change == "gate-after":
            circuit.z(0)
        if change == "reset-after":
            circuit.reset(0)
    with pytest.raises(AssertionError, match="measurement|Measured|Classical"):
        checker()(lambda: circuit)


def test_incoherent_mixture_with_correct_diagonal_is_rejected():
    from qiskit.quantum_info import Kraus

    projectors = []
    for index in range(8):
        projector = np.zeros((8, 8), dtype=complex)
        projector[index, index] = 1
        projectors.append(projector)
    circuit = preparation()
    circuit.append(Kraus(projectors).to_instruction(), range(3))
    # Channels are outside the explicitly admitted Gate/reset/initialize prefix.
    with pytest.raises(AssertionError, match="preparation"):
        checker()(lambda: measured(circuit))


def test_density_oracle_checks_coherence_in_addition_to_populations():
    scope = {}
    exec(compile(revision().CHECK, "<authored-task66-check>", "exec"), scope)
    diagonal = np.zeros((8, 8), dtype=complex)
    diagonal[(1, 2, 4), (1, 2, 4)] = 1 / 3
    with pytest.raises(AssertionError, match="W state"):
        scope["assert_w_density"](diagonal)


def test_nonfinite_parameter_metadata_and_declared_resource_bounds_are_checked():
    circuit = measured(preparation())
    item = circuit.data[-1]
    operation = item.operation.to_mutable()
    operation.params = [np.inf]
    circuit.data[-1] = item.replace(operation=operation)
    with pytest.raises(AssertionError, match="Nonfinite"):
        checker()(lambda: circuit)
    circuit = measured(preparation())
    for _ in range(1024):
        circuit.barrier()
    with pytest.raises(AssertionError, match="expansion"):
        checker()(lambda: circuit)
    inner = preparation()
    for _ in range(17):
        operation = Gate("nested", 3, [])
        operation.definition = inner
        inner = QuantumCircuit(3)
        inner.append(operation, range(3))
    with pytest.raises(AssertionError, match="depth"):
        checker()(lambda: measured(inner))


def test_sixteen_explicit_definition_levels_are_within_public_bound():
    inner = preparation()
    for _ in range(16):
        operation = Gate("nested", 3, [])
        operation.definition = inner
        inner = QuantumCircuit(3)
        inner.append(operation, range(3))
    checker()(lambda: measured(inner))


@pytest.mark.parametrize("bound", ["instructions", "depth"])
def test_generic_controlled_definition_cannot_bypass_expansion_bounds(bound):
    from qiskit.circuit import ControlledGate

    base = QuantumCircuit(2).to_gate()
    body = QuantumCircuit(3)
    if bound == "instructions":
        for _ in range(1025):
            body.id(1)
    else:
        for _ in range(16):
            operation = Gate("nested", 3, [])
            operation.definition = body
            body = QuantumCircuit(3)
            body.append(operation, range(3))
    controlled = ControlledGate("authored", 3, [], definition=body, base_gate=base)
    circuit = QuantumCircuit(3)
    circuit.append(controlled, range(3))
    circuit.compose(preparation(), inplace=True)
    with pytest.raises(AssertionError, match="expansion|depth"):
        checker()(lambda: measured(circuit))


@pytest.mark.parametrize("control_state", [0, 1])
def test_generic_controlled_effective_definitions_preserve_open_control_and_phase(control_state):
    # A phase on the base becomes relative when controlled; it cannot be dropped.
    base = QuantumCircuit(2)
    base.cx(0, 1)
    base.cx(0, 1)
    for phase in (0, 0.37):
        base.global_phase = phase
        controlled = base.to_gate().control(1, ctrl_state=control_state, annotated=False)
        circuit = preparation()
        circuit.append(controlled, range(3))
        measured(circuit)
        if phase:
            with pytest.raises(AssertionError, match="W state"):
                checker()(lambda circuit=circuit: circuit)
        else:
            checker()(lambda circuit=circuit: circuit)


@pytest.mark.parametrize("kind", ["parameter", "delay", "control-flow", "width", "category"])
def test_invalid_output_domains_fail_without_accepting_a_plausible_count_law(kind):
    from qiskit.circuit import Parameter

    circuit = preparation()
    if kind == "parameter":
        circuit.rz(Parameter("angle"), 0)
    elif kind == "delay":
        circuit.delay(100, 0)
    elif kind == "control-flow":
        circuit = QuantumCircuit(3, 3)
        circuit.compose(preparation(), inplace=True)
        with circuit.if_test((circuit.clbits[0], True)):
            circuit.x(0)
    elif kind == "width":
        circuit = QuantumCircuit(4)
    else:
        circuit = np.zeros(8)
    with pytest.raises(AssertionError):
        checker()(lambda: measured(circuit) if type(circuit) is QuantumCircuit else circuit)


@pytest.mark.skipif(not CACHE, reason="Needs pinned source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_exact_source_revision_and_pre_generation_campaign_binding(suite, model):
    from graybench.campaign_setup import CampaignSetup, build_setup
    from graybench.evaluation_campaign import validate_cohort

    api = revision()
    source = load_suite(suite, Path(CACHE))[66]
    judge = recipe_judge(api.TRACK, image=IMAGE)
    task = judge.revise(source)
    assert task.digest != source.digest and judge.revise(task) == task
    assert task.canonical_solution == source.canonical_solution
    assert api.REQUIREMENT in task.public.prompt
    with pytest.raises(ValueError, match="Revise"):
        judge.configuration(source)
    for field in ("upstream_test", "canonical_solution"):
        with pytest.raises(ValueError, match="exact pinned"):
            judge.revise(source.model_copy(update={field: "changed"}))
    setup = build_setup("W-development", model, (source,), IMAGE, evaluation_recipe=api.TRACK)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    tasks = restored.tasks(Path(CACHE))
    assert tasks == (task,)
    validate_cohort(restored.protocol, tasks, restored.judge())
    _, manifest = restored.judge().configuration(task)
    assert manifest["release_eligible"] is False
    assert manifest["source_task_digest"] == source.digest
    assert manifest["public_contract_digest"] == task.public.digest


@pytest.mark.parametrize(
    "kwargs",
    [
        {"protocol": 3},
        {"graph_transport": "snapshot-v1"},
        {"graph_batch": "safe-v1"},
        {"output_limit": 1024},
        {"graph_state_limit": 1024},
        {"graph_limits": "implicit"},
    ],
)
def test_transport_is_frozen(kwargs):
    with pytest.raises(ValueError):
        recipe_judge(revision().TRACK, image=IMAGE, **kwargs)


@pytest.mark.skipif(not CACHE, reason="Needs pinned source")
def test_providers_receive_revised_public_contract_without_private_answer():
    import json

    from graybench.contracts import ModelSpec
    from graybench.providers import BUILTINS, adapter

    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[66]
        task = recipe_judge(revision().TRACK, image=IMAGE).revise(source)
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
            body = json.dumps(prepared.body, ensure_ascii=False)
            assert json.dumps(task.public.prompt, ensure_ascii=False)[1:-1] in body
            assert json.dumps(task.upstream_test, ensure_ascii=False)[1:-1] not in body
            assert json.dumps(source.canonical_solution, ensure_ascii=False)[1:-1] not in body
            assert prepared.digest != provider.prepare(model, source.public, None).digest


@pytest.mark.skipif(not CACHE, reason="Needs pinned source")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_full_authored_roster_transfers_all_correct_constructions(suite, monkeypatch):
    from collections import Counter

    from graybench.graph_anchors import PublicAnchorRegistry

    module = evidence_module("task66_state_verification", monkeypatch)
    source = load_suite(suite, Path(CACHE))[66]
    task = module.revised_task(source)
    probes = module.probes(source)
    assert Counter(p.expectation for p in probes) == {"pass": 16, "fail": 26}
    anchors = PublicAnchorRegistry.capture()
    unsupported = []
    for probe in probes:
        graph = module.graph_trial(checker(), module.authored(task, probe), anchors)
        host = module.verdict(checker(), module.authored(task, probe))
        assert host["outcome"] == probe.expectation and host["calls"] == 1
        if graph["support"] == "unsupported":
            unsupported.append(probe.name)
            assert probe.expectation == "pass" and graph["oracle"] is None
        else:
            assert graph["oracle"] == host
            assert graph["request_within_wire_limit"]
            assert graph["response_within_wire_limit"]
            assert graph["expanded_snapshot_within_state_limit"]
    assert unsupported == []  # No correct construction in this roster may be dropped.


@pytest.mark.skipif(not CACHE, reason="Needs pinned source")
def test_isolated_roster_is_frozen_before_execution(tmp_path, monkeypatch):
    import json
    import sys
    from collections import Counter

    module = evidence_module("task66_state_controls", monkeypatch)
    output = tmp_path / "controls.jsonl"

    class BeforeExecution(Exception):
        pass

    def stop(_judge, _task, _completion):
        header = json.loads(output.read_text().splitlines()[0])["event"]
        selection = header["selection"]
        assert Counter(case["expectation"] for case in selection["cases"].values()) == {
            "pass": 32,
            "fail": 52,
        }
        assert len(selection["declared_judges"]) == 2
        for manifest in selection["declared_judges"].values():
            assert manifest["track"] == revision().TRACK
            assert manifest["release_eligible"] is False
        raise BeforeExecution

    monkeypatch.setattr(module.ControlsJudge, "evaluate", stop)
    monkeypatch.setattr(
        sys,
        "argv",
        ["task66-controls", "--cache", CACHE, "--image", IMAGE, "--output", str(output)],
    )
    with pytest.raises(BeforeExecution):
        module.main()


@pytest.mark.skipif(not CACHE, reason="Needs pinned source")
def test_host_evidence_replay_and_source_changes_fail_closed(monkeypatch):
    import copy

    module = evidence_module("task66_state_verification", monkeypatch)
    declared = module.plan(Path(CACHE))
    report = module.build(Path(CACHE), declared)
    assert report["host_outcomes"] == {"pass": 32, "fail": 52}
    assert report["graph_support"] == {"supported": 84}
    assert report["density_oracle_entry_mutants_rejected"] == 128
    assert report["release_eligible"] is False
    assert module.verify(report, declared, Path(CACHE))
    changed = copy.deepcopy(report)
    changed["controls"][0]["host"]["outcome"] = "fail"
    with pytest.raises(ValueError, match="recreation"):
        module.verify(changed, declared, Path(CACHE))
    changed = copy.deepcopy(declared)
    changed["engine_source"]["digest"] = "0" * 64
    with pytest.raises(ValueError, match="predeclared"):
        module.build(Path(CACHE), changed)


def test_decode_protocol_failure_is_not_labeled_unsupported(monkeypatch):
    from graybench.circuit_wire import WireError
    from graybench.graph_anchors import PublicAnchorRegistry

    module = evidence_module("task66_state_verification", monkeypatch)
    original = module.DeltaGraphArena.prepare
    calls = 0

    def corrupt_response(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise WireError("Injected decoder protocol failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(module.DeltaGraphArena, "prepare", corrupt_response)
    with pytest.raises(WireError, match="decoder protocol"):
        module.graph_trial(
            checker(), lambda: measured(preparation()), PublicAnchorRegistry.capture()
        )


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_TASK66_TEST_IMAGE"),
    reason="Explicit Task66 immutable control image and pinned cache required",
)
def test_complete_isolated_roster_matches_declared_outcomes(monkeypatch):
    module = evidence_module("task66_state_controls", monkeypatch)
    judge = module.ControlsJudge(image=os.environ["GRAYBENCH_TASK66_TEST_IMAGE"])
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[66]
        for probe in module.probes(source):
            result = judge.evaluate(source, probe.completion)
            assert result.outcome == probe.expectation, (suite, probe.name, result.evidence)

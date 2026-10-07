import os

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import DiagonalGate, UCRXGate, UCRYGate, UCRZGate
from qiskit.circuit.library.generalized_gates.uc_pauli_rot import UCPauliRotGate
from qiskit.quantum_info import Operator
from test_graph_converted_instructions import arenas, transfer

from graybench.circuit_wire import WireError


@pytest.mark.parametrize("cached", [False, True])
def test_diagonal_keeps_raw_parameters_and_definition_without_revalidation(cached):
    source, target = arenas()
    gate = DiagonalGate([1, 1j, -1, -1j])
    definition = gate.definition if cached else None
    circuit = QuantumCircuit(2)
    circuit.append(gate, [0, 1], copy=False)
    parameters = gate.params
    parameters[0] = 0.25  # The transport must not repair or re-run the constructor.
    remote, operation, attrs, params, body = transfer(
        source, target, (circuit, gate, vars(gate), parameters, definition)
    )
    assert type(operation) is DiagonalGate and vars(operation) is attrs
    assert operation.params is params and params[0] == 0.25
    assert operation._definition is body
    assert remote.data[0].operation is operation and remote.data[0].params[0] == 1
    if cached:
        assert all(type(item.operation) is UCRZGate for item in body.data)
    params[1] = 0.5
    assert transfer(target, source, remote) is circuit
    assert gate.params is parameters and parameters[1] == 0.5
    assert gate._definition is definition and circuit.data[0].params[1] == 1j


@pytest.mark.parametrize(
    "factory", [UCRXGate, UCRYGate, UCRZGate, lambda p: UCPauliRotGate(p, "Z")]
)
def test_uniform_rotation_preserves_raw_axis_and_cached_definition(factory):
    source, target = arenas()
    gate = factory([0.2, -0.3])
    definition = gate.definition
    expected = Operator(definition).data.copy()
    gate.rot_axes = "changed-after-definition"
    gate.params[0] = 0.9
    remote, attrs, params, body = transfer(
        source, target, (gate, vars(gate), gate.params, definition)
    )
    assert type(remote) is type(gate) and vars(remote) is attrs and remote.params is params
    assert remote._definition is body and remote.rot_axes == "changed-after-definition"
    np.testing.assert_allclose(Operator(remote).data, expected, atol=1e-12, rtol=0)
    params.append(0.7)
    assert transfer(target, source, remote) is gate
    assert gate.params[-1] == 0.7 and gate._definition is definition


def test_diagonal_does_not_synthesize_a_definition_during_transfer():
    source, target = arenas()
    gate = DiagonalGate([1, 1j])
    remote = transfer(source, target, gate)
    assert gate._definition is None and remote._definition is None
    np.testing.assert_allclose(Operator(remote).data, np.diag([1, 1j]), atol=1e-12, rtol=0)
    cached = remote.definition
    assert transfer(target, source, remote) is gate
    assert gate._definition is not None
    assert transfer(source, target, gate, sequence=2) is remote
    assert remote._definition is cached


@pytest.mark.parametrize("mutation", ["axis", "class", "extra"])
def test_uniform_rotation_forgery_is_rejected_before_live_update(mutation):
    source, target = arenas()
    gate = UCRZGate([0.2, -0.3])
    remote = transfer(source, target, gate)
    gate.label = "updated"
    snapshot = source.snapshot({"value": gate}, sequence=2)
    state = next(row for row in snapshot["nodes"] if row["kind"] == "python_instruction")["state"]
    if mutation == "axis":
        state["rot_axes"] = 17
        attributes = next(
            row for row in snapshot["nodes"] if row["id"] == state["attributes"]["ref"]
        )
        next(entry for entry in attributes["state"] if entry[0] == "rot_axes")[1] = 17
    elif mutation == "class":
        state["class"] = "ucrx"
    else:
        state["unexpected"] = None
    with pytest.raises(WireError):
        target.prepare(snapshot, sequence=2)
    assert remote.label is None and type(remote) is UCRZGate and remote.rot_axes == "Z"


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
@pytest.mark.parametrize("transport", ["snapshot-v1", "delta-v1"])
@pytest.mark.parametrize("wrong_diagonal", [False, True])
def test_protected_diagonal_cached_definition_survives_following_call(transport, wrong_diagonal):
    from test_graph_bridge import task

    from graybench.upstream import UpstreamJudge

    check = """import numpy as np
from qiskit.quantum_info import Operator
def check(candidate):
    gate, params = candidate()
    assert gate.params is params and gate._definition is None
    np.testing.assert_allclose(Operator(gate).data, np.diag([1,1j]), atol=1e-12, rtol=0)
    cached = gate.definition
    params[0] = 0.25
    returned = candidate(gate)
    assert returned is gate and gate.definition is cached and gate.params is params
    assert params == [0.25, 0.5]
    np.testing.assert_allclose(Operator(gate).data, np.diag([1,1j]), atol=1e-12, rtol=0)
"""
    code = """from qiskit.circuit.library import DiagonalGate
held = None
def answer(gate=None):
    global held
    if gate is not None:
        assert gate is held and gate._definition is not None
        gate.params[1] = 0.5
        return gate
    held = DiagonalGate(DIAGONAL)
    return held, held.params
""".replace("DIAGONAL", "[1,1]" if wrong_diagonal else "[1,1j]")
    result = UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
        graph_transport=transport,
    ).evaluate(task(check), code)
    assert result.outcome == ("fail" if wrong_diagonal else "pass"), result.evidence.get("detail")

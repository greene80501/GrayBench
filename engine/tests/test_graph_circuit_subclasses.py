import os

import numpy as np
import pytest
from qiskit.circuit.library import QFT, GraphState
from qiskit.quantum_info import Operator
from test_graph_converted_instructions import arenas, transfer

from graybench.circuit_wire import WireError

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.mark.parametrize("built", [False, True])
def test_qft_preserves_lazy_state_and_dictionary_without_building(built):
    source, target = arenas()
    circuit = QFT(3, approximation_degree=1, do_swaps=False, insert_barriers=True)
    if built:
        circuit._build()
    data = circuit._data
    remote, attrs, storage = transfer(source, target, (circuit, vars(circuit), data))
    assert type(remote) is QFT
    assert vars(remote) is attrs and remote._data is storage
    assert circuit._data is data and circuit._is_built is built
    assert remote._is_built is built
    assert remote._builder_api.circuit is remote
    assert remote.approximation_degree == 1 and not remote.do_swaps
    np.testing.assert_allclose(Operator(remote).data, Operator(circuit).data)
    restored = transfer(target, source, remote)
    assert restored is circuit and restored._is_built


def test_qft_invalidation_preserves_detached_storage_and_rebuilds_remotely():
    source, target = arenas()
    circuit = QFT(3)
    circuit._build()
    held = circuit._data
    remote, detached = transfer(source, target, (circuit, held))
    remote.do_swaps = False
    assert not remote._is_built and remote._data is not detached
    restored, old = transfer(target, source, (remote, detached))
    assert restored is circuit and old is held and circuit._data is not held
    assert not circuit._is_built and not circuit.do_swaps
    expected = Operator(QFT(3, do_swaps=False)).data
    np.testing.assert_allclose(Operator(circuit).data, expected)


def test_graph_state_preserves_class_matrix_alias_and_cached_definition():
    source, target = arenas()
    circuit = GraphState([[0, 1], [1, 0]])
    gate = circuit.data[0].operation
    definition = gate.definition
    matrix = gate.adjacency_matrix
    matrix[0, 1] = 0
    remote, operation, array, body = transfer(source, target, (circuit, gate, matrix, definition))
    assert type(remote) is GraphState
    assert remote.data[0].operation is operation
    assert operation.adjacency_matrix is array and operation.definition is body
    assert array[0, 1] == 0
    assert body.count_ops()["cz"] == 1
    assert transfer(target, source, remote) is circuit


@pytest.mark.parametrize("mutation", ["flag", "unknown_class", "extra_field"])
def test_qft_malformed_state_rejected_without_changing_live_name(mutation):
    source, target = arenas()
    circuit = QFT(2, name="before")
    remote = transfer(source, target, circuit)
    circuit.name = "after"
    snapshot = source.snapshot({"value": circuit}, sequence=2)
    state = next(r["state"] for r in snapshot["nodes"] if r["kind"] == "quantum_circuit")
    if mutation == "flag":
        state["_is_built"] = 1
        attrs = next(r["state"] for r in snapshot["nodes"] if r["id"] == state["attributes"]["ref"])
        next(pair for pair in attrs if pair[0] == "_is_built")[1] = 1
    elif mutation == "unknown_class":
        state["class"] = "arbitrary.circuit.Class"
    else:
        state["extra"] = None
    with pytest.raises(WireError):
        target.prepare(snapshot, sequence=2)
    assert remote.name == "before" and not remote._is_built


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
@pytest.mark.parametrize("transport", ["snapshot-v1", "delta-v1"])
@pytest.mark.parametrize("wrong_swaps", [False, True])
def test_protected_qft_lazy_build_and_following_call(transport, wrong_swaps):
    from test_graph_bridge import task

    from graybench.upstream import UpstreamJudge

    check = """from qiskit.circuit.library import QFT
from qiskit.quantum_info import Operator
import numpy as np
def check(candidate):
    circuit, attrs = candidate()
    assert type(circuit) is QFT and vars(circuit) is attrs
    assert not circuit._is_built and circuit.do_swaps
    original = circuit._data
    expected = Operator(QFT(3)).data
    np.testing.assert_allclose(Operator(circuit).data, expected)
    circuit.do_swaps = False
    assert not circuit._is_built and circuit._data is not original
    returned = candidate(circuit)
    assert returned is circuit and vars(circuit) is attrs and circuit._is_built
    np.testing.assert_allclose(Operator(circuit).data, Operator(QFT(3, do_swaps=False)).data)
"""
    code = """from qiskit.circuit.library import QFT
held = None
def answer(circuit=None):
    global held
    if circuit is None:
        held = QFT(3, do_swaps=SWAPS)
        return held, vars(held)
    assert circuit is held and not circuit._is_built and not circuit.do_swaps
    circuit._build()
    return circuit
""".replace("SWAPS", str(not wrong_swaps))
    result = UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
        graph_transport=transport,
    ).evaluate(task(check), code)
    assert result.outcome == ("fail" if wrong_swaps else "pass"), result.evidence.get("detail")


def test_circuit_subclass_change_is_rejected_before_live_mutation():
    source, target = arenas()
    circuit = GraphState([[0, 1], [1, 0]])
    remote = transfer(source, target, circuit)
    snapshot = source.snapshot({"value": circuit}, sequence=2)
    record = next(
        r
        for r in snapshot["nodes"]
        if r["kind"] == "quantum_circuit" and r["state"].get("class") == "graph_state"
    )
    del record["state"]["class"]
    with pytest.raises(WireError):
        target.prepare(snapshot, sequence=2)
    assert type(remote) is GraphState

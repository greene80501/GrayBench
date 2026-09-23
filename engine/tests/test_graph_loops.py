"""Loop bodies, index sets and parameters have independent native snapshots."""

import copy
import os

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import ForLoopOp, Parameter
from qiskit.converters import circuit_to_dag, dag_to_circuit

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def transfer(value):
    sender, receiver = (
        GraphArena(side=side, session="loops", limits=GraphLimits())
        for side in ("judge", "candidate")
    )
    return receiver.commit(
        receiver.prepare(sender.snapshot({"value": value}, sequence=1), sequence=1)
    )["value"]


@pytest.mark.parametrize("indices", [range(1, 8, 2), (1, 3, 5)])
def test_for_loop_preserves_python_aliases_and_separate_cached_values(indices):
    qc = QuantumCircuit(1, 1)
    body = QuantumCircuit(1, 1)
    parameter = Parameter("iteration")
    body.rx(parameter, 0)
    operation = ForLoopOp(indices, parameter, body)
    qc.append(operation, qc.qubits, qc.clbits, copy=False)
    body.z(0)
    operation.params[0] = (7, 9)

    # Native getters produce fresh wrappers, even for the cached loop parameter.
    native = qc.data[0]
    assert native.params[1] == parameter and native.params[1] is not parameter
    assert native.params[2].count_ops() == {"rx": 1}
    remote, gate, original, held_parameter = transfer((qc, operation, body, parameter))
    assert remote.data[0].operation is gate
    assert gate.params[2] is original
    assert gate.params[1] is held_parameter
    assert gate.params[0] == (7, 9)
    assert original.count_ops() == {"rx": 1, "z": 1}
    first, second = remote.data[0].params, remote.data[0].params
    assert type(first[0]) is (range if type(indices) is range else list)
    assert list(first[0]) == list(indices)
    assert first[1] == held_parameter and first[1] is not held_parameter
    assert first[1] is not second[1]
    assert first[2] is not second[2]
    assert first[2].count_ops() == {"rx": 1}


def test_nested_while_loop_keeps_break_and_continue_in_cached_body():
    qc = QuantumCircuit(1, 1)
    with qc.while_loop((qc.clbits[0], 1)):
        with qc.if_test((qc.clbits[0], 1)) as otherwise:
            qc.break_loop()
        with otherwise:
            qc.continue_loop()
    remote = transfer(qc)
    cached = remote.data[0].params[0]
    branches = cached.data[0].params
    assert branches[0].count_ops() == {"break_loop": 1}
    assert branches[1].count_ops() == {"continue_loop": 1}


def test_range_root_preserves_equal_distinct_objects_and_descriptors():
    first, second = range(1, 5, 2), range(1, 6, 2)
    same = range(1, 5, 2)
    remote = transfer([first, first, same, second])
    assert remote[0] is remote[1]
    assert remote[0] == remote[2] and remote[0] is not remote[2]
    assert (remote[3].start, remote[3].stop, remote[3].step) == (1, 6, 2)


@pytest.mark.parametrize("loop", ["for", "while"])
def test_compiled_loops_keep_fresh_outer_wrappers(loop):
    qc = QuantumCircuit(1, 1)
    context = qc.for_loop(range(3)) if loop == "for" else qc.while_loop((qc.clbits[0], 1))
    with context:
        qc.x(0)
        qc.break_loop()
    qc = dag_to_circuit(circuit_to_dag(qc))
    assert qc.data[0].operation is not qc.data[0].operation
    remote = transfer(qc)
    assert remote.data[0].operation is not remote.data[0].operation
    body = remote.data[0].params[-1]
    assert body.count_ops() == {"x": 1, "break_loop": 1}


@pytest.mark.parametrize("fault", ["zero_step", "extra_field", "missing_body", "wrong_parameter"])
def test_malformed_loop_rejected_before_live_mutation(fault):
    sender, receiver = (
        GraphArena(side=s, session="bad-loop", limits=GraphLimits()) for s in ("judge", "candidate")
    )
    qc = QuantumCircuit(1)
    with qc.for_loop(range(3)) as index:
        qc.rx(index, 0)
    remote = receiver.commit(
        receiver.prepare(sender.snapshot({"value": qc}, sequence=1), sequence=1)
    )["value"]
    wire = copy.deepcopy(sender.snapshot({"value": qc}, sequence=2))
    state = next(
        n["state"]
        for n in wire["nodes"]
        if n["kind"] == "circuit_data" and n["state"]["operations"][0]["name"] == "for_loop"
    )
    op = state["operations"][0]
    if fault == "zero_step":
        op["indices"]["step"] = 0
    elif fault == "extra_field":
        op["indices"]["callable"] = "unsafe"
    elif fault == "missing_body":
        op["branches"] = []
    else:
        op["loop_parameter"] = {"kind": "literal", "value": 1}
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=2)
    assert remote.data[0].params[0] == range(3)
    assert remote.data[0].params[-1].count_ops() == {"rx": 1}


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Immutable image required")
def test_protected_parameterized_loop_and_conditional_break_matches_native():
    from test_graph_bridge import judge

    code = """from math import pi
def answer(qc):
    with qc.for_loop(range(3)) as index:
        qc.ry(pi / 3 * index, 0)
        qc.measure(0, 0)
        with qc.if_test((qc.clbits[0], 1)):
            qc.break_loop()
    return qc
"""
    test = """from qiskit import QuantumCircuit
def check(candidate):
    qc = QuantumCircuit(1, 1)
    assert candidate(qc) is qc
    indices, parameter, body = qc.data[0].params
    assert indices == range(3)
    assert parameter in body.parameters
    assert body.count_ops() == {'ry': 1, 'measure': 1, 'if_else': 1}
    assert body.data[-1].params[0].count_ops() == {'break_loop': 1}
"""
    namespace = {}
    exec(code, namespace)
    exec(test, namespace)
    namespace["check"](namespace["answer"])
    result = judge(test, code)
    assert result.outcome == "pass", result

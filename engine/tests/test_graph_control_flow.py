"""Control-flow transport must preserve Python state and native branch snapshots."""

import contextlib
import os

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Gate, IfElseOp
from qiskit.circuit.library import CXGate
from qiskit.converters import circuit_to_dag, dag_to_circuit

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_wire import GraphArena, GraphLimits


def transfer(a, b, value):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=1), sequence=1))["value"]


@pytest.mark.parametrize("anchored", [False, True])
def test_nested_if_context_updates_previously_exported_circuit(anchored):
    from graybench.graph_anchors import PublicAnchorRegistry

    registry = PublicAnchorRegistry.capture() if anchored else None
    a, b = (
        GraphArena(side=s, session="input-control", limits=GraphLimits(), anchors=registry)
        for s in ("judge", "candidate")
    )
    qc = QuantumCircuit(2, 3)
    qc.x(0)
    remote, gate = transfer(a, b, (qc, CXGate() if anchored else Gate("custom", 2, [])))
    with contextlib.ExitStack() as stack:
        for index in (0, 2):
            stack.enter_context(remote.if_test((index, 1)))
        remote.append(gate, [0, 1])
    assert transfer(b, a, remote) is qc
    assert qc.count_ops() == {"x": 1, "if_else": 1}


def test_if_else_keeps_original_blocks_separate_from_native_branch_snapshots():
    a, b = (
        GraphArena(side=s, session="control-flow", limits=GraphLimits())
        for s in ("judge", "candidate")
    )
    qc = QuantumCircuit(1, 1)
    body = QuantumCircuit(1, 1)
    body.x(0)
    op = IfElseOp((qc.clbits[0], 1), body)
    qc.append(op, qc.qubits, qc.clbits, copy=False)
    body.h(0)
    op.condition = (qc.clbits[0], 0)

    remote, gate, original = transfer(a, b, (qc, op, body))
    assert remote.data[0].operation is gate
    assert gate.blocks[0] is original
    assert original.count_ops() == {"x": 1, "h": 1}
    assert gate.condition[1] == 0
    held = remote.data[0].params[0]
    assert held is not remote.data[0].params[0]
    assert held.count_ops() == {"x": 1}
    held.z(0)
    assert remote.data[0].params[0].count_ops() == {"x": 1}
    native = dag_to_circuit(circuit_to_dag(remote))
    assert native.data[0].operation.condition[1] == 1
    assert transfer(b, a, remote) is qc
    assert body.count_ops() == {"x": 1, "h": 1}


def test_branch_operation_limit_is_shared_by_sibling_branches():
    qc = QuantumCircuit(1, 1)
    body = QuantumCircuit(1, 1)
    for _ in range(2048):
        body.x(0)
    qc.append(IfElseOp((qc.clbits[0], 1), body, body), qc.qubits, qc.clbits)
    arena = GraphArena(side="judge", session="limit", limits=GraphLimits())
    with pytest.raises(WireLimitError, match="operation tree"):
        arena.snapshot({"value": qc}, sequence=1)


def test_malformed_nested_branch_rejected_before_live_mutation():
    a, b = (
        GraphArena(side=s, session="malformed-control", limits=GraphLimits())
        for s in ("judge", "candidate")
    )
    qc = QuantumCircuit(1, 1)
    body = QuantumCircuit(1, 1)
    body.x(0)
    qc.append(IfElseOp((qc.clbits[0], 1), body), qc.qubits, qc.clbits)
    remote = transfer(a, b, qc)
    wire = a.snapshot({"value": qc}, sequence=2)
    data = next(n for n in wire["nodes"] if n["kind"] == "circuit_data")
    data["state"]["operations"][0]["branches"][0]["operations"][0]["qubits"] = [8]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert remote.data[0].params[0].count_ops() == {"x": 1}


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Immutable image required")
def test_protected_nested_if_else_preserves_original_and_cached_branches():
    from test_graph_bridge import judge

    code = """from qiskit import QuantumCircuit
from qiskit.circuit import IfElseOp
def answer():
    qc = QuantumCircuit(1,1)
    body = QuantumCircuit(1,1)
    with body.if_test((body.clbits[0],1)):
        body.x(0)
    op = IfElseOp((qc.clbits[0],1),body)
    qc.append(op,qc.qubits,qc.clbits,copy=False)
    body.h(0)
    return qc,op,body
"""
    test = """def check(candidate):
    qc,op,body=candidate()
    assert qc.data[0].operation is op and op.blocks[0] is body
    assert body.count_ops() == {'if_else':1,'h':1}
    assert qc.data[0].params[0].count_ops() == {'if_else':1}
    assert qc.data[0].params[0].data[0].params[0].count_ops() == {'x':1}
"""
    namespace = {}
    exec(code, namespace)
    exec(test, namespace)
    namespace["check"](namespace["answer"])
    result = judge(test, code)
    assert result.outcome == "pass", result


def test_if_else_native_branches_retain_shared_python_leaf_operations():
    a, b = (
        GraphArena(side=s, session="control-leaf", limits=GraphLimits())
        for s in ("judge", "candidate")
    )
    qc = QuantumCircuit(1, 1)
    body = QuantumCircuit(1, 1)
    leaf = Gate("custom", 1, [1])
    body.append(leaf, [0], copy=False)
    op = IfElseOp((qc.clbits[0], 1), body)
    qc.append(op, qc.qubits, qc.clbits, copy=False)

    remote, held = transfer(a, b, (qc, leaf))
    first = remote.data[0].params[0]
    second = remote.data[0].params[0]
    assert first is not second
    assert first.data[0].operation is second.data[0].operation is held
    held.params[0] = 7
    assert first.data[0].params == [1]
    assert transfer(b, a, remote) is qc
    assert leaf.params == [7]


@pytest.mark.parametrize("register", [False, True])
def test_compiled_nested_if_else_keeps_fresh_wrappers_and_both_branches(register):
    a, b = (
        GraphArena(side=s, session="compiled-control", limits=GraphLimits())
        for s in ("judge", "candidate")
    )
    qc = QuantumCircuit(1, 1)
    body = QuantumCircuit(1, 1)
    with body.if_test((body.clbits[0], 1)):
        body.x(0)
    alternate = QuantumCircuit(1, 1)
    alternate.z(0)
    condition = (qc.cregs[0] if register else qc.clbits[0], 1)
    qc.append(IfElseOp(condition, body, alternate, label="branch"), qc.qubits, qc.clbits)
    qc = dag_to_circuit(circuit_to_dag(qc))
    assert qc.data[0].operation is not qc.data[0].operation
    remote = transfer(a, b, qc)
    assert remote.data[0].operation is not remote.data[0].operation
    assert remote.data[0].label == "branch"
    assert len(remote.data[0].params) == 2
    assert remote.data[0].params[0].data[0].params[0].count_ops() == {"x": 1}
    assert remote.data[0].params[1].count_ops() == {"z": 1}
    assert transfer(b, a, remote) is qc

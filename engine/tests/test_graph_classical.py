"""Classical expression roots and native cached conditions have separate identity."""

import copy
import os
from uuid import UUID

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import IfElseOp
from qiskit.circuit.classical import expr, types
from qiskit.converters import circuit_to_dag, dag_to_circuit

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_classical import encode, restore, validate
from graybench.graph_wire import GraphArena, GraphLimits


def test_classical_condition_keeps_root_alias_and_native_snapshot():
    qc = QuantumCircuit(1, 2)
    body = QuantumCircuit(1, 2)
    body.x(0)
    original = expr.bit_xor(qc.clbits[0], qc.clbits[1])
    operation = IfElseOp(original, body)
    qc.append(operation, qc.qubits, qc.clbits, copy=False)
    operation.condition = expr.logic_not(original)

    # Native control: the original root is retained, while branch instructions
    # cache the earlier Binary condition independently of Python mutation.
    native = dag_to_circuit(circuit_to_dag(qc, copy_operations=False), copy_operations=False)
    assert native.data[0].operation.condition == original
    assert type(operation.condition) is expr.Unary
    assert original.left is not original.left

    sender, receiver = (
        GraphArena(side=side, session="classical", limits=GraphLimits())
        for side in ("judge", "candidate")
    )
    wire = sender.snapshot({"value": (qc, operation, operation.condition, original)}, sequence=1)
    remote, gate, condition, held_original = receiver.commit(receiver.prepare(wire, sequence=1))[
        "value"
    ]
    assert remote.data[0].operation is gate
    assert gate.condition is condition
    assert condition == operation.condition
    assert held_original == original
    assert held_original.left is not held_original.left
    assert held_original.left.var == remote.clbits[0]
    assert held_original.right.var == remote.clbits[1]
    cached = dag_to_circuit(circuit_to_dag(remote, copy_operations=False), copy_operations=False)
    assert cached.data[0].operation.condition == held_original
    assert type(cached.data[0].operation.condition) is expr.Binary


def expressions():
    qc = QuantumCircuit(1, 3)
    bit = expr.lift(qc.clbits[0])
    register = expr.lift(qc.cregs[0])
    return [
        bit,
        register,
        expr.Value(1.25, types.Float()),
        expr.lift(True),
        expr.Var(UUID(int=1), types.Uint(3), name="memory"),
        expr.Stretch(UUID(int=2), "delay"),
        expr.Cast(bit, types.Uint(3), implicit=True),
        expr.logic_not(bit),
        expr.bit_xor(bit, expr.lift(qc.clbits[1])),
        expr.Index(register, expr.Value(1, types.Uint(2)), types.Bool()),
    ]


@pytest.mark.parametrize("original", expressions())
def test_expression_roots_roundtrip_without_interning_equal_wrappers(original):
    a, b = (
        GraphArena(side=s, session="roots", limits=GraphLimits()) for s in ("judge", "candidate")
    )
    equal_wrapper = restore(encode(original))
    assert equal_wrapper is not original
    roots = {"value": [original, original, equal_wrapper]}
    remote = b.commit(b.prepare(a.snapshot(roots, sequence=1), sequence=1))["value"]
    assert remote[0] is remote[1]
    assert type(remote[0]) is type(original)
    assert remote[0] == original
    assert remote[2] == remote[0] and remote[2] is not remote[0]
    restored = a.commit(a.prepare(b.snapshot({"value": remote}, sequence=2), sequence=2))["value"]
    assert restored[0] is original


@pytest.mark.parametrize(
    "fault", ["unknown_kind", "extra_field", "bad_op", "bad_width", "bad_target"]
)
def test_malformed_classical_tree_rejected_before_live_mutation(fault):
    a, b = (
        GraphArena(side=s, session="invalid", limits=GraphLimits()) for s in ("judge", "candidate")
    )
    value = [expr.bit_xor(expr.lift(True), expr.lift(False))]
    remote = b.commit(b.prepare(a.snapshot({"value": value}, sequence=1), sequence=1))["value"]
    previous = remote[0]
    wire = copy.deepcopy(a.snapshot({"value": value}, sequence=2))
    state = next(n["state"] for n in wire["nodes"] if n["kind"] == "classical_expression")
    if fault == "unknown_kind":
        state["kind"] = "__import__"
    elif fault == "extra_field":
        state["callable"] = "unsafe"
    elif fault == "bad_op":
        state["op"] = 999
    elif fault == "bad_width":
        state["type"] = {"kind": "Uint", "width": -1}
    else:
        state["left"] = {
            "kind": "Var",
            "type": {"kind": "Bool"},
            "name": None,
            "var": {"kind": "uuid", "value": "invalid"},
        }
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert remote[0] is previous


def test_classical_depth_limit_remains_a_resource_outcome():
    state = encode(expr.lift(True))
    for _ in range(17):
        state = {"kind": "Unary", "type": {"kind": "Bool"}, "op": 2, "operand": state}
    with pytest.raises(WireLimitError):
        validate(state)


def test_classical_node_budget_is_shared_by_sibling_subtrees():
    state = encode(expr.lift(True))
    for _ in range(12):
        state = {"kind": "Binary", "type": {"kind": "Bool"}, "op": 3, "left": state, "right": state}
    with pytest.raises(WireLimitError):
        validate(state)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Immutable image required")
def test_protected_classical_condition_matches_native():
    from test_graph_bridge import judge

    code = """from qiskit.circuit.classical import expr
def answer(qc):
    with qc.if_test(expr.bit_xor(qc.clbits[0], qc.clbits[1])):
        qc.x(0)
    return qc
"""
    test = """from qiskit import QuantumCircuit
from qiskit.circuit.classical import expr
def check(candidate):
    qc = QuantumCircuit(1, 2)
    result = candidate(qc)
    assert result is qc
    assert qc.data[0].operation.condition == expr.bit_xor(qc.clbits[0], qc.clbits[1])
    assert qc.data[0].params[0].count_ops() == {'x': 1}
"""
    scope = {}
    exec(code, scope)
    exec(test, scope)
    scope["check"](scope["answer"])
    result = judge(test, code)
    assert result.outcome == "pass", result

import numpy as np
import pytest
from qiskit.circuit import Parameter, ParameterExpression, ParameterVector
from qiskit.quantum_info import SparsePauliOp

from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="expr", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, seq=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=seq), sequence=seq))["value"]


@pytest.mark.parametrize(
    "form", ["add", "cancel", "sin", "power", "complex", "bound", "zero", "negative_zero"]
)
def test_expression_type_value_parameter_set_and_stable_resnapshot(form):
    p = Parameter("p")
    forms = {
        "add": p + 1,
        "cancel": p - p,
        "sin": (p + 2).sin(),
        "power": p**2,
        "complex": p + 1j,
        "bound": (p + 1).bind({p: 2}),
        "zero": ParameterExpression({}, "0"),
        "negative_zero": ParameterExpression({}, "-0.0"),
    }
    e = forms[form]
    a, b = arenas()
    result = transfer(a, b, e)
    assert type(result) is ParameterExpression
    assert result == e and result.parameters == e.parameters
    assert transfer(b, a, result) is e
    assert transfer(a, b, e, 2) is result
    if form == "negative_zero":
        assert np.signbit(result.numeric())


def test_expression_vector_getters_retain_actual_vector_after_shrink():
    v = ParameterVector("v", 3)
    e = v[0] + v[2]
    v.resize(1)
    a, b = arenas()
    expr, remote = transfer(a, b, (e, v))
    assert all(p.vector is remote for p in expr.parameters)
    assert {p.index for p in expr.parameters} == {0, 2}
    remote.resize(0)
    assert transfer(b, a, expr) is e
    assert len(v) == 0
    assert transfer(a, b, e, 2) is expr


def test_sparse_symbolic_operators_share_actual_coefficient_nodes_and_views():
    p = Parameter("p")
    left = SparsePauliOp(["X", "Z"], coeffs=np.array([p, p], dtype=object))
    # Qiskit creates distinct expression wrappers; preserve actual stored identity.
    assert left.coeffs[0] is not left.coeffs[1]
    right = left.copy()
    right._coeffs = left.coeffs
    held = left.coeffs[0]
    a, b = arenas()
    x, y, expr, array = transfer(a, b, (left, right, held, left.coeffs))
    assert x.coeffs is y.coeffs is array and array[0] is expr
    assert array[0] is not array[1] and array[0] == array[1]
    array[0] = array[1]
    transfer(b, a, (x, y))
    assert left.coeffs is right.coeffs and left.coeffs[0] is left.coeffs[1]
    assert left.coeffs[0] is not held


@pytest.mark.parametrize("mutation", ["unknown", "stack", "power", "divide", "literal", "nested"])
def test_malformed_expression_rejected_before_exported_container_changes(mutation):
    from graybench.circuit_wire import WireError

    a, b = arenas()
    values = [1]
    held = transfer(a, b, values)
    values.append(2)
    p = Parameter("p")
    wire = a.snapshot({"value": (values, p + 1)}, sequence=2)
    state = next(n for n in wire["nodes"] if n["kind"] == "parameter_expression")["state"]

    def lit(x):
        return {"kind": "literal", "value": x}

    if mutation == "unknown":
        state["program"][0]["op"] = "__import__"
    elif mutation == "stack":
        state["program"][0]["lhs"] = None
        state["program"][0]["rhs"] = None
    elif mutation == "power":
        state["program"] = [{"op": "POW", "lhs": lit(2), "rhs": lit(1000000)}]
    elif mutation == "divide":
        state["program"] = [{"op": "DIV", "lhs": lit(1), "rhs": lit(0)}]
    elif mutation == "literal":
        state["program"][0]["lhs"] = lit(True)
    else:
        nested = lit(1)
        for _ in range(18):
            nested = {
                "kind": "expression",
                "program": [{"op": "ADD", "lhs": nested, "rhs": lit(1)}],
            }
        state["program"][0]["lhs"] = nested
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert held == [1]


def test_noncanonical_replay_rejected_at_prepare():
    from graybench.circuit_wire import WireError

    a, b = arenas()
    wire = a.snapshot({"value": ParameterExpression({}, "3")}, sequence=1)
    state = wire["nodes"][0]["state"]
    state["program"] = [
        {
            "op": "ADD",
            "lhs": {"kind": "literal", "value": 1},
            "rhs": {"kind": "literal", "value": 2},
        }
    ]
    with pytest.raises(WireError, match="canonical"):
        b.prepare(wire, sequence=1)


def test_conflicting_parameter_names_are_wire_errors():
    from graybench.circuit_wire import WireError

    a, b = arenas()
    p, q = Parameter("p"), Parameter("q")
    wire = a.snapshot({"value": p + q}, sequence=1)
    state = wire["nodes"][0]["state"]
    state["program"][0]["rhs"]["name"] = state["program"][0]["lhs"]["name"]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=1)

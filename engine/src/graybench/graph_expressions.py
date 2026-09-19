"""Bounded fixed-operation expression replay with real vector graph references."""

import json
import math
from dataclasses import dataclass
from uuid import UUID

from graybench.circuit_wire import WireError, fields
from graybench.graph_symbolic import SYMBOL_CODECS, name_value, uuid_value
from graybench.symbolic_wire import BINARY, UNARY


def literal(value):
    from graybench.graph_types import scalar_value

    result = scalar_value(value)
    if type(result) not in (int, float, complex):
        raise WireError("Invalid symbolic numeric literal")
    if type(result) is int and result.bit_length() > 1024:
        raise WireError("Symbolic integer exceeds limit")
    return result


def encode(value, ref, depth=0, budget=None):
    from qiskit.circuit import Parameter, ParameterExpression, ParameterVectorElement

    from graybench.graph_types import scalar_record

    budget = [4096] if budget is None else budget
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise WireError("Expression structure exceeds limit")
    if type(value) in (Parameter, ParameterVectorElement):
        state = SYMBOL_CODECS[
            "parameter" if type(value) is Parameter else "parameter_vector_element"
        ].state(value, ref)
        return dict(state, kind="symbol" if type(value) is Parameter else "element")
    if type(value) is not ParameterExpression:
        encoded = scalar_record(value)
        literal(encoded)
        return {"kind": "literal", "value": encoded}
    steps = []
    for step in value._qpy_replay:
        op = str(step.op).removeprefix("OpCode.")
        if op not in BINARY and op not in UNARY:
            raise WireError("Unsupported expression operation")
        steps.append(
            {
                "op": op,
                "lhs": None if step.lhs is None else encode(step.lhs, ref, depth + 1, budget),
                "rhs": None if step.rhs is None else encode(step.rhs, ref, depth + 1, budget),
            }
        )
        if len(steps) > 512:
            raise WireError("Expression program exceeds limit")
    if not steps:
        encoded = scalar_record(value.numeric())
        literal(encoded)
        steps = [
            {
                "op": "ADD",
                "lhs": {"kind": "literal", "value": encoded},
                "rhs": {"kind": "literal", "value": 0},
            }
        ]
    return {"kind": "expression", "program": steps}


def validate(value, index, depth=0, budget=None):
    budget = [4096] if budget is None else budget
    budget[0] -= 1
    if depth > 16 or budget[0] < 0 or type(value) is not dict:
        raise WireError("Invalid or excessive expression structure")
    kind = value.get("kind")
    if kind == "literal":
        fields(value, {"kind", "value"})
        literal(value["value"])
        return
    if kind in ("symbol", "element"):
        expected = {"kind", "name", "uuid"}
        if kind == "element":
            expected |= {"vector", "index"}
        fields(value, expected)
        name_value(value["name"])
        uuid_value(value["uuid"])
        if kind == "element":
            SYMBOL_CODECS["parameter_vector_element"].validate(
                {k: v for k, v in value.items() if k != "kind"}, index
            )
        return
    fields(value, {"kind", "program"})
    program = value["program"]
    if kind != "expression" or type(program) is not list or not 1 <= len(program) <= 512:
        raise WireError("Invalid expression program")
    count = 0
    for step in program:
        budget[0] -= 1
        if budget[0] < 0:
            raise WireError("Expression operation budget exceeded")
        fields(step, {"op", "lhs", "rhs"})
        op = step["op"]
        if type(op) is not str or (op not in BINARY and op not in UNARY):
            raise WireError("Unknown expression operation")
        for operand in (step["lhs"], step["rhs"]):
            if operand is not None:
                validate(operand, index, depth + 1, budget)
                count += 1
        arity = 2 if op in BINARY else 1
        if count < arity:
            raise WireError("Expression stack underflow")
        count += 1 - arity
    if count != 1:
        raise WireError("Expression did not produce one result")


def vector_tokens(value):
    kind = value["kind"]
    if kind == "element":
        yield value["vector"]
    elif kind == "expression":
        for step in value["program"]:
            for operand in (step["lhs"], step["rhs"]):
                if operand is not None:
                    yield from vector_tokens(operand)


def replay(value, resolve):
    from qiskit.circuit import Parameter, ParameterExpression, ParameterVectorElement
    from qiskit.exceptions import QiskitError

    from graybench.graph_types import scalar_record

    kind = value["kind"]
    if kind == "literal":
        return literal(value["value"])
    if kind == "symbol":
        return Parameter(value["name"], uuid=UUID(value["uuid"]))
    if kind == "element":
        return ParameterVectorElement(
            resolve(value["vector"]["ref"]), value["index"], uuid=UUID(value["uuid"])
        )
    stack = []
    for step in value["program"]:
        for operand in (step["lhs"], step["rhs"]):
            if operand is not None:
                stack.append(replay(operand, resolve))
        op = step["op"]
        try:
            if op in BINARY:
                right, left = stack.pop(), stack.pop()
                exponent = left if op == "RPOW" else right
                if (
                    op in {"POW", "RPOW"}
                    and type(exponent) in (int, float, complex)
                    and abs(exponent) > 64
                ):
                    raise WireError("Numeric expression exponent exceeds limit")
                result = BINARY[op](left, right)
            else:
                operand = stack.pop()
                if type(operand) in (int, float, complex):
                    operand = ParameterExpression({}, "0") + operand
                result = UNARY[op](operand)
            if type(result) in (int, float, complex):
                literal(scalar_record(result))
            stack.append(result)
        except (
            ArithmeticError,
            ValueError,
            TypeError,
            AttributeError,
            IndexError,
            QiskitError,
        ) as exc:
            raise WireError("Invalid expression replay") from exc
    result = stack[0]
    if type(result) is not ParameterExpression:
        result = ParameterExpression({}, "0") + result
    # Native arithmetic may generate nonfinite constants internally.
    if not result.parameters:
        numeric = result.numeric()
        if not (math.isfinite(numeric.real) and math.isfinite(numeric.imag)):
            raise WireError("Nonfinite expression result")
    return result


@dataclass(frozen=True)
class ExpressionCodec:
    kind: str = "parameter_expression"
    immutable: bool = True

    def matches(self, value):
        from qiskit.circuit import ParameterExpression

        return type(value) is ParameterExpression

    def state(self, value, ref):
        return encode(value, ref)

    def validate(self, state, index):
        validate(state, index)
        if state["kind"] != "expression":
            raise WireError("Expression node requires expression state")

    def tokens(self, state):
        return vector_tokens(state)

    def allocate(self, state, index):
        return None

    def populate(self, target, state, resolve):
        result = replay(state, resolve)
        vectors = {id(resolve(token["ref"])): token for token in vector_tokens(state)}
        actual = encode(result, lambda value: vectors[id(value)])
        if json.dumps(actual, sort_keys=True) != json.dumps(state, sort_keys=True):
            raise WireError("Noncanonical expression replay")
        return result

    def validate_update(self, previous, state):
        pass

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()

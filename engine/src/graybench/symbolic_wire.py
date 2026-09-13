"""Bounded symbolic replay for pinned Qiskit 2.4, without expression-string evaluation.

The transport stores explicit parameters and a fixed arithmetic operation vocabulary.
ParameterVectorElement retains its vector identity and ordering, not just its printed name.
Qiskit's structured _qpy_replay is inspected only during encoding; no QPY bytes are decoded.
"""

import math
import operator
from numbers import Number
from uuid import UUID

try:
    from .circuit_wire import WireError, fields, number
except ImportError:
    from circuit_wire import WireError, fields, number

BINARY = {
    "ADD": operator.add,
    "SUB": operator.sub,
    "MUL": operator.mul,
    "DIV": operator.truediv,
    "POW": operator.pow,
    "RSUB": lambda a, b: b - a,
    "RDIV": lambda a, b: b / a,
    "RPOW": lambda a, b: b**a,
}
UNARY = {
    "SIN": lambda x: x.sin(),
    "COS": lambda x: x.cos(),
    "TAN": lambda x: x.tan(),
    "ASIN": lambda x: x.arcsin(),
    "ACOS": lambda x: x.arccos(),
    "ATAN": lambda x: x.arctan(),
    "EXP": lambda x: x.exp(),
    "LOG": lambda x: x.log(),
    "SIGN": lambda x: x.sign(),
    "CONJ": lambda x: x.conjugate(),
    "ABS": abs,
}


def encode_parameter(value, depth=0):
    import numpy as np
    from qiskit.circuit import Parameter, ParameterExpression, ParameterVectorElement

    if depth > 16:
        raise WireError("Symbolic nesting exceeds limit")
    if isinstance(value, np.generic):
        if value.dtype.kind not in "iufc" or not np.isfinite(value):
            raise WireError("Invalid NumPy gate parameter")
        try:
            from .scientific_wire import encode_scientific
        except ImportError:
            from scientific_wire import encode_scientific
        return encode_scientific(value)
    if isinstance(value, ParameterVectorElement):
        vector = value.vector
        return {
            "kind": "vector_element_v1",
            "name": vector.name,
            "length": len(vector),
            "root_uuid": str(vector._root_uuid),
            "index": value.index,
            "uuid": str(value.uuid),
        }
    if isinstance(value, Parameter):
        return {"kind": "parameter_v1", "name": value.name, "uuid": str(value.uuid)}
    if isinstance(value, ParameterExpression):
        program = []
        for step in value._qpy_replay:
            name = str(step.op).removeprefix("OpCode.")
            if name not in BINARY and name not in UNARY:
                raise WireError("Unsupported symbolic operation: " + name)
            program.append(
                {
                    "op": name,
                    "lhs": None if step.lhs is None else encode_parameter(step.lhs, depth + 1),
                    "rhs": None if step.rhs is None else encode_parameter(step.rhs, depth + 1),
                }
            )
            if len(program) > 512:
                raise WireError("Symbolic program exceeds limit")
        if not program:
            return number(value.numeric())
        return {"kind": "expression_v1", "program": program}
    return number(value)


def decode_parameter(value, context=None, depth=0, budget=None):
    import numpy as np
    from qiskit.circuit import Parameter, ParameterVector

    if context is None:
        context = {"parameters": {}, "vectors": {}}
    if budget is None:
        budget = [4096]
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise WireError("Symbolic structure exceeds limit")
    if type(value) in (float, int):
        return number(value)
    if type(value) is not dict:
        raise WireError("Invalid symbolic value")
    kind = value.get("kind")
    if kind == "numpy_scalar_v1":
        import numpy as np

        try:
            from .scientific_wire import decode_scientific
        except ImportError:
            from scientific_wire import decode_scientific
        scalar = decode_scientific(value)
        if scalar.dtype.kind not in "iufc" or not np.isfinite(scalar):
            raise WireError("Invalid NumPy gate parameter")
        return scalar
    if kind in ("parameter_v1", "vector_element_v1"):
        expected = {"kind", "name", "uuid"}
        if kind == "vector_element_v1":
            expected |= {"length", "root_uuid", "index"}
        fields(value, expected)
        name = value["name"]
        if type(name) is not str or not 1 <= len(name) <= 256 or type(value["uuid"]) is not str:
            raise WireError("Invalid parameter identity")
        try:
            uid = UUID(value["uuid"])
        except ValueError as exc:
            raise WireError("Invalid parameter UUID") from exc
        if kind == "parameter_v1":
            signature = (kind, name)
            parameter = None
        else:
            length, index = value["length"], value["index"]
            if (
                type(length) is not int
                or not 1 <= length <= 4096
                or type(index) is not int
                or not 0 <= index < length
                or type(value["root_uuid"]) is not str
            ):
                raise WireError("Invalid parameter vector dimensions")
            try:
                root = UUID(value["root_uuid"])
            except ValueError as exc:
                raise WireError("Invalid vector UUID") from exc
            if root.int + length - 1 >= 2**128 or uid.int != root.int + index:
                raise WireError("Vector element UUID does not match its root and index")
            key = str(root)
            signature = (kind, name, length, index, key)
            old = context["vectors"].get(key)
            if old is not None and old[:2] != (name, length):
                raise WireError("Conflicting parameter vector identity")
            if old is None:
                if sum(v[1] for v in context["vectors"].values()) + length > 8192:
                    raise WireError("Total parameter-vector allocation exceeds limit")
                vector = ParameterVector(name, 0)
                vector._root_uuid = root
                vector.resize(length)
                context["vectors"][key] = (name, length, vector)
            parameter = context["vectors"][key][2][index]
        old = context["parameters"].get(str(uid))
        if old is not None:
            if old[0] != signature:
                raise WireError("Conflicting parameter UUID identity")
            return old[1]
        if parameter is None:
            if len(context["parameters"]) >= 8192:
                raise WireError("Parameter count exceeds limit")
            parameter = Parameter(name, uuid=uid)
        context["parameters"][str(uid)] = (signature, parameter)
        return parameter
    fields(value, {"kind", "program"})
    if (
        kind != "expression_v1"
        or type(value["program"]) is not list
        or not 1 <= len(value["program"]) <= 512
    ):
        raise WireError("Invalid symbolic program")
    stack = []
    for step in value["program"]:
        fields(step, {"op", "lhs", "rhs"})
        op = step["op"]
        if type(op) is not str or (op not in BINARY and op not in UNARY):
            raise WireError("Operation is not in the fixed symbolic registry")
        for operand in (step["lhs"], step["rhs"]):
            if operand is not None:
                stack.append(decode_parameter(operand, context, depth + 1, budget))
        try:
            if op in BINARY:
                right, left = stack.pop(), stack.pop()
                exponent = left if op == "RPOW" else right
                numeric_exponent = exponent.item() if isinstance(exponent, np.generic) else exponent
                if (
                    op in {"POW", "RPOW"}
                    and isinstance(numeric_exponent, Number)
                    and abs(numeric_exponent) > 64
                ):
                    raise WireError("Numeric exponent exceeds symbolic codec limit")
                result = BINARY[op](left, right)
            else:
                result = UNARY[op](stack.pop())
            if type(result) in (int, float):
                number(result)
            elif isinstance(result, np.generic):
                if not np.isfinite(result):
                    raise WireError("Non-finite numeric replay result")
            elif type(result) is complex:
                if not math.isfinite(result.real) or not math.isfinite(result.imag):
                    raise WireError("Non-finite numeric replay result")
            stack.append(result)
        except (IndexError, ArithmeticError, AttributeError, TypeError, ValueError) as exc:
            raise WireError("Invalid symbolic replay: " + str(exc)) from exc
    if len(stack) != 1:
        raise WireError("Symbolic replay did not produce exactly one value")
    return stack[0]

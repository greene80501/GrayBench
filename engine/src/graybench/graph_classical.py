"""Bounded intrinsic classical ASTs; only held root wrappers are graph nodes."""

import math
from dataclasses import dataclass

from graybench.circuit_wire import WireError, WireLimitError, fields, integer
from graybench.graph_circuit import CIRCUIT_CODECS, bit_state, restore_bit, validate_bit
from graybench.graph_symbolic import name_value, uuid_value

REGISTER = CIRCUIT_CODECS["qiskit_register"]
CHILDREN = {
    "Var": (),
    "Value": (),
    "Stretch": (),
    "Cast": ("operand",),
    "Unary": ("operand",),
    "Binary": ("left", "right"),
    "Index": ("target", "index"),
}


def charge(depth, budget):
    budget[0] -= 1
    if depth > 16 or budget[0] < 0:
        raise WireLimitError("Classical expression tree exceeds limit")


def encode_type(value):
    from qiskit.circuit.classical import types

    for name in ("Bool", "Uint", "Float", "Duration"):
        if type(value) is getattr(types, name):
            return {"kind": name, **({"width": value.width} if name == "Uint" else {})}
    raise WireError("Unsupported classical type")


def restore_type(state):
    from qiskit.circuit.classical import types

    if type(state) is not dict or state.get("kind") not in ("Bool", "Uint", "Float", "Duration"):
        raise WireError("Invalid classical type")
    name = state["kind"]
    fields(state, {"kind", "width"} if name == "Uint" else {"kind"})
    if name == "Uint":
        width = integer(state["width"], 1024)
        if width == 0:
            raise WireError("Zero classical integer width")
        return types.Uint(width)
    return {"Bool": types.Bool, "Float": types.Float, "Duration": types.Duration}[name]()


def encode(value, *, depth=0, budget=None):
    from uuid import UUID

    from qiskit.circuit import ClassicalRegister, Clbit
    from qiskit.circuit.classical import expr

    budget = [4096] if budget is None else budget
    charge(depth, budget)
    name = type(value).__name__
    if name not in CHILDREN or type(value) is not getattr(expr, name):
        raise WireError("Unsupported classical expression")
    state = {"kind": name, "type": encode_type(value.type)}
    for child in CHILDREN[name]:
        state[child] = encode(getattr(value, child), depth=depth + 1, budget=budget)
    if name in ("Var", "Stretch"):
        target = value.var
        if type(target) is UUID:
            state["var"] = {"kind": "uuid", "value": str(target)}
        elif type(target) is Clbit:
            state["var"] = {"kind": "bit", "value": bit_state(target)}
        elif type(target) is ClassicalRegister:
            state["var"] = {"kind": "register", "value": REGISTER.state(target, None)}
        else:
            raise WireError("Unsupported classical variable target")
        state["name"] = value.name
    elif name == "Value":
        state["value"] = value.value
    elif name in ("Unary", "Binary"):
        state["op"] = value.op.value
    elif name == "Cast":
        state["implicit"] = value.implicit
    return state


def restore(state, *, depth=0, budget=None):
    from qiskit.circuit.classical import expr, types

    budget = [4096] if budget is None else budget
    charge(depth, budget)
    if (
        type(state) is not dict
        or type(state.get("kind")) is not str
        or state["kind"] not in CHILDREN
    ):
        raise WireError("Invalid classical expression kind")
    name = state["kind"]
    extra = (
        {"var", "name"}
        if name in ("Var", "Stretch")
        else (
            {"value"}
            if name == "Value"
            else {"op"}
            if name in ("Unary", "Binary")
            else {"implicit"}
            if name == "Cast"
            else set()
        )
    )
    fields(state, {"kind", "type"} | set(CHILDREN[name]) | extra)
    native_type = restore_type(state["type"])
    children = [restore(state[key], depth=depth + 1, budget=budget) for key in CHILDREN[name]]
    if name in ("Var", "Stretch"):
        var = state["var"]
        fields(var, {"kind", "value"})
        if state["name"] is not None:
            name_value(state["name"])
        if var["kind"] == "uuid":
            target = uuid_value(var["value"])
        elif var["kind"] == "bit":
            validate_bit(var["value"])
            if var["value"]["family"] != "c":
                raise WireError("Classical variable requires a classical bit")
            target = restore_bit(var["value"])
        elif var["kind"] == "register":
            REGISTER.validate(var["value"], {})
            if var["value"]["family"] != "c":
                raise WireError("Classical variable requires a classical register")
            target = REGISTER.allocate(var["value"], {})
        else:
            raise WireError("Invalid classical variable target")
        if name == "Stretch":
            if (
                var["kind"] != "uuid"
                or type(native_type) is not types.Duration
                or state["name"] is None
            ):
                raise WireError("Invalid stretch variable")
            return expr.Stretch(target, state["name"])
        return expr.Var(target, native_type, name=state["name"])
    if name == "Value":
        value = state["value"]
        if (
            type(value) not in (int, float)
            or (type(value) is int and value.bit_length() > 1024)
            or (type(value) is float and not math.isfinite(value))
        ):
            raise WireError("Unsupported classical literal")
        return expr.Value(value, native_type)
    if name in ("Unary", "Binary"):
        operation = integer(state["op"], 17 if name == "Binary" else 3)
        if operation == 0:
            raise WireError("Invalid classical operation")
        cls = expr.Binary if name == "Binary" else expr.Unary
        return cls(cls.Op(operation), *children, native_type)
    if name == "Cast":
        if type(state["implicit"]) is not bool:
            raise WireError("Invalid classical cast flag")
        return expr.Cast(children[0], native_type, implicit=state["implicit"])
    return expr.Index(*children, native_type)


def validate(state):
    try:
        rebuilt = restore(state)
        if encode(rebuilt) != state:
            raise WireError("Noncanonical classical expression")
    except WireError:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise WireError("Invalid classical expression state") from exc


@dataclass(frozen=True)
class ClassicalExpressionCodec:
    kind: str = "classical_expression"
    immutable: bool = True

    def matches(self, value):
        from qiskit.circuit.classical import expr

        return type(value) in tuple(getattr(expr, name) for name in CHILDREN)

    def state(self, value, ref):
        state = encode(value)
        validate(state)
        return state

    def validate(self, state, index):
        validate(state)

    def tokens(self, state):
        return ()

    def allocate(self, state, index):
        return restore(state)

    def populate(self, target, state, resolve):
        return target

    def validate_update(self, previous, state):
        pass

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()

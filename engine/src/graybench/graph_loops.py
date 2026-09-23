"""Fixed loop index sets, distinct from retained Python parameter containers."""

import math
from dataclasses import dataclass

from graybench.circuit_wire import WireError, WireLimitError, fields


def encode_indices(value):
    if type(value) is range:
        return {"kind": "range", "start": value.start, "stop": value.stop, "step": value.step}
    if type(value) is list:
        return {"kind": "values", "values": list(value)}
    raise WireError("Unsupported cached loop index set")


def restore_indices(state):
    if type(state) is not dict:
        raise WireError("Invalid loop index set")
    if state.get("kind") == "range":
        fields(state, {"kind", "start", "stop", "step"})
        for key in ("start", "stop", "step"):
            if type(state[key]) is not int or state[key].bit_length() > 1024:
                raise WireError("Invalid range integer")
        if state["step"] == 0:
            raise WireError("Zero range step")
        return range(state["start"], state["stop"], state["step"])
    fields(state, {"kind", "values"})
    if state["kind"] != "values" or type(state["values"]) is not list:
        raise WireError("Invalid loop index values")
    if len(state["values"]) > 4096:
        raise WireLimitError("Loop index set exceeds limit")
    for value in state["values"]:
        if (
            type(value) not in (int, float)
            or (type(value) is int and value.bit_length() > 1024)
            or (type(value) is float and not math.isfinite(value))
        ):
            raise WireError("Invalid loop index value")
    return list(state["values"])


@dataclass(frozen=True)
class RangeCodec:
    kind: str = "range"
    immutable: bool = True

    def matches(self, value):
        return type(value) is range

    def state(self, value, ref):
        return encode_indices(value)

    def validate(self, state, index):
        if type(restore_indices(state)) is not range:
            raise WireError("Range node requires range state")

    def tokens(self, state):
        return ()

    def allocate(self, state, index):
        return restore_indices(state)

    def populate(self, target, state, resolve):
        return target

    def validate_update(self, previous, state):
        pass

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()

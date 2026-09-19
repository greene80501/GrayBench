"""Symbol identities and mutable vector ownership for the experimental graph.

Rust-backed parameter UUID getters produce temporary Python UUID wrappers; those
are intrinsic descriptors, not exported child identities. Vector slots are real
Python references and are transported as nodes. No UUID-based object interning.
"""

from dataclasses import dataclass
from functools import cache
from uuid import UUID, SafeUUID

from graybench.circuit_wire import WireError, fields
from graybench.graph_scientific import node


@cache
def classes():
    from qiskit.circuit import Parameter, ParameterVector, ParameterVectorElement

    return {
        "uuid": UUID,
        "parameter": Parameter,
        "parameter_vector": ParameterVector,
        "parameter_vector_element": ParameterVectorElement,
    }


def uuid_value(value):
    if type(value) is not str or len(value) != 36:
        raise WireError("Invalid symbolic UUID")
    try:
        uid = UUID(value)
    except ValueError as exc:
        raise WireError("Invalid symbolic UUID") from exc
    if str(uid) != value:
        raise WireError("Noncanonical symbolic UUID")
    return uid


def name_value(value):
    if type(value) is not str or len(value) > 256:
        raise WireError("Invalid symbolic name")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise WireError("Symbolic name is not UTF-8") from exc
    return value


@dataclass(frozen=True)
class SymbolCodec:
    kind: str

    @property
    def immutable(self):
        return self.kind != "parameter_vector"

    def matches(self, value):
        return type(value) is classes()[self.kind]

    def state(self, value, ref):
        if self.kind == "uuid":
            if type(value.is_safe) is not SafeUUID:
                raise WireError("Unsupported UUID safety flag")
            return {"uuid": str(value), "safe": value.is_safe.name}
        if self.kind == "parameter_vector":
            return {
                "name": value.name,
                "params": ref(value.params),
                "root_uuid": ref(value._root_uuid),
            }
        state = {"name": value.name, "uuid": str(value.uuid)}
        if self.kind == "parameter_vector_element":
            state.update(vector=ref(value.vector), index=value.index)
        return state

    def validate(self, state, index):
        if self.kind == "uuid":
            fields(state, {"uuid", "safe"})
            uuid_value(state["uuid"])
            if type(state["safe"]) is not str or state["safe"] not in SafeUUID.__members__:
                raise WireError("Invalid UUID safety flag")
        elif self.kind == "parameter_vector":
            fields(state, {"name", "params", "root_uuid"})
            name_value(state["name"])
            params = node(state["params"], index, {"list"})["state"]
            if type(params) is not list or len(params) > 4096:
                raise WireError("Invalid or oversized parameter vector list")
            root = node(state["root_uuid"], index, {"uuid"})["state"]
            SYMBOL_CODECS["uuid"].validate(root, index)
        else:
            expected = {"name", "uuid"}
            if self.kind == "parameter_vector_element":
                expected |= {"vector", "index"}
            fields(state, expected)
            name_value(state["name"])
            uuid_value(state["uuid"])
            if self.kind == "parameter_vector_element":
                vector = node(state["vector"], index, {"parameter_vector"})["state"]
                # Independent structural validation: incoming record order is untrusted.
                SYMBOL_CODECS["parameter_vector"].validate(vector, index)
                if type(state["index"]) is not int or not 0 <= state["index"] < 4096:
                    raise WireError("Invalid parameter vector element index")
                if state["name"] != f"{vector['name']}[{state['index']}]":
                    raise WireError("Renamed parameter vector element is unsupported")

    def tokens(self, state):
        if self.kind == "parameter_vector":
            return (state["params"], state["root_uuid"])
        if self.kind == "parameter_vector_element":
            return (state["vector"],)
        return ()

    def allocate(self, state, index):
        if self.kind == "parameter_vector_element":
            return None
        if self.kind == "uuid":
            return UUID(state["uuid"], is_safe=SafeUUID[state["safe"]])
        if self.kind == "parameter":
            return classes()[self.kind](state["name"], uuid=UUID(state["uuid"]))
        result = object.__new__(classes()[self.kind])
        # Only the name is needed by the element constructor. Slot references are
        # resolved before commit, without changing any existing vector.
        result._name = state["name"]
        return result

    def populate(self, target, state, resolve):
        return classes()[self.kind](
            resolve(state["vector"]["ref"]), state["index"], uuid=UUID(state["uuid"])
        )

    def prepare(self, state, resolve, index):
        return (resolve(state["params"]["ref"]), resolve(state["root_uuid"]["ref"]))

    def apply(self, target, prepared):
        target._params, target._root_uuid = prepared

    def validate_update(self, previous, state):
        if self.kind == "parameter_vector" and previous["name"] != state["name"]:
            raise WireError("Exported parameter vector rename is unsupported")

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()


SYMBOL_CODECS = {
    name: SymbolCodec(name)
    for name in ("uuid", "parameter", "parameter_vector", "parameter_vector_element")
}

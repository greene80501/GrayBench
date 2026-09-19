"""Qiskit primitive component references, including actual stored mappings/lists."""

import math
from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError, fields, integer
from graybench.graph_scientific import (
    array_state,
    node,
    pauli_shape,
    shape_dims,
    tuple_items,
    validate_attributes,
)
from graybench.primitive_wire import data_fields, shape_tuple
from graybench.scientific_wire import MAX_BYTES


@cache
def classes():
    from qiskit.primitives import BitArray, DataBin, PrimitiveResult, PubResult, SamplerPubResult

    return dict(
        bit_array=BitArray,
        data_bin=DataBin,
        primitive_result=PrimitiveResult,
        pub_result=PubResult,
        sampler_pub_result=SamplerPubResult,
    )


ATTRIBUTES = {
    "bit_array": (("array", "_array"), ("num_bits", "_num_bits"), ("shape", "_shape")),
    "data_bin": (("data", "_data"), ("shape", "_shape")),
    "primitive_result": (("pubs", "_pub_results"), ("metadata", "_metadata")),
    "pub_result": (("data", "_data"), ("metadata", "_metadata")),
    "sampler_pub_result": (("data", "_data"), ("metadata", "_metadata")),
}


def mapping_entries(token, index):
    entries = node(token, index, {"dict"})["state"]
    if type(entries) is not list:
        raise WireError("Invalid DataBin mapping state")
    result = {}
    for pair in entries:
        if (
            type(pair) is not list
            or len(pair) != 2
            or type(pair[0]) is not str
            or pair[0] in result
        ):
            raise WireError("Invalid DataBin mapping entry")
        result[pair[0]] = pair[1]
    data_fields(result)
    return result


def leading_shape(token, index):
    if type(token) is not dict or set(token) != {"ref"}:
        return None
    if type(token["ref"]) is not str or token["ref"] not in index:
        raise WireError("Invalid DataBin field reference")
    record = index[token["ref"]]
    kind, state = record["kind"], record["state"]
    if kind in {"ndarray_owner", "ndarray_view"}:
        return array_state(token, index)[0]
    if kind == "numpy_scalar":
        return ()
    if kind in {"bit_array", "data_bin"}:
        fields(state, {key for key, _ in ATTRIBUTES[kind]} | {"attributes"})
        return shape_tuple(tuple_items(state["shape"], index))
    if kind == "op_shape":
        left, right = shape_dims(state, index)
        if not left and not right:
            return (1, 1)
        return (math.prod(left), math.prod(right)) if right else (math.prod(left),)
    if kind == "pauli_list":
        return pauli_shape(state, index)
    return None  # Other admitted classes have no shape attribute in the pinned SDK.


@dataclass(frozen=True)
class PrimitiveCodec:
    kind: str
    immutable: bool = False

    def matches(self, value):
        return type(value) is classes()[self.kind]

    def state(self, value, ref):
        names = ATTRIBUTES[self.kind]
        if self.kind in {"bit_array", "primitive_result"}:
            if set(vars(value)) != {attribute for _, attribute in names}:
                raise WireError("Extra primitive instance state requires a graph codec")
        if self.kind == "sampler_pub_result" and vars(value):
            raise WireError("Extra sampler-result instance state requires a graph codec")
        result = {key: ref(getattr(value, attribute)) for key, attribute in names}
        if self.kind != "pub_result":
            result["attributes"] = ref(vars(value))
        return result

    def validate(self, state, shape_index):
        expected = {key for key, _ in ATTRIBUTES[self.kind]}
        if self.kind != "pub_result":
            expected |= {"attributes"}
        fields(state, expected)
        if self.kind in {"bit_array", "primitive_result"}:
            validate_attributes(state, shape_index, ATTRIBUTES[self.kind])
        elif self.kind == "sampler_pub_result":
            validate_attributes(state, shape_index, ())
        if self.kind == "bit_array":
            bits = integer(state["num_bits"], MAX_BYTES * 8)
            actual, dtype = array_state(state["array"], shape_index)
            shape = shape_tuple(tuple_items(state["shape"], shape_index))
            if (
                dtype.str != "|u1"
                or len(actual) < 2
                or actual[-1] != (bits + 7) // 8
                or actual[:-2] != shape
            ):
                raise WireError("BitArray packed dtype/shape differs from its metadata")
            return
        if self.kind == "data_bin":
            values = mapping_entries(state["data"], shape_index)
            mapping_entries(state["attributes"], shape_index)
            shape = shape_tuple(tuple_items(state["shape"], shape_index))
            for token in values.values():
                actual = leading_shape(token, shape_index)
                if actual is not None and actual[: len(shape)] != shape:
                    raise WireError("DataBin field leading shape differs from container shape")
            return
        node(state["metadata"], shape_index, {"dict"})
        if self.kind == "primitive_result":
            node(state["pubs"], shape_index, {"list"})
        else:
            node(state["data"], shape_index, {"data_bin"})

    def tokens(self, state):
        yield from (state[key] for key, _ in ATTRIBUTES[self.kind])
        if self.kind != "pub_result":
            yield state["attributes"]

    def allocate(self, state, shape_index):
        return object.__new__(classes()[self.kind])

    def prepare(self, state, resolve, shape_index):
        from graybench.graph_types import token_value

        values = tuple(token_value(state[key], resolve) for key, _ in ATTRIBUTES[self.kind])
        attrs = resolve(state["attributes"]["ref"]) if self.kind != "pub_result" else None
        return values, attrs

    def apply(self, target, prepared):
        values, attrs = prepared
        if self.kind not in {"bit_array", "primitive_result"}:
            for (_, attribute), value in zip(ATTRIBUTES[self.kind], values, strict=True):
                object.__setattr__(target, attribute, value)
        if attrs is not None:
            # Names were checked against fixed fields or DataBin's restricted-name
            # contract. This attaches the actual dictionary node, preserving aliases.
            object.__setattr__(target, "__dict__", attrs)

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()

    def validate_update(self, previous, state):
        pass


PRIMITIVE_CODECS = {kind: PrimitiveCodec(kind) for kind in ATTRIBUTES}

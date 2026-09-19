"""Bounded data-only Qiskit primitive containers; no jobs or executable objects."""

import math

try:
    from .circuit_wire import WireError, WireLimitError, fields, integer
    from .scientific_wire import MAX_BYTES, array_record, decode_array
except ImportError:
    from circuit_wire import WireError, WireLimitError, fields, integer
    from scientific_wire import MAX_BYTES, array_record, decode_array


def data_fields(data):
    from qiskit.primitives import DataBin

    if type(data) is not dict or any(
        type(key) is not str or key.startswith("__") or key in DataBin._RESTRICTED_NAMES
        for key in data
    ):
        raise WireError("Invalid or reserved DataBin field name")
    if len(data) > 1024 or any(len(key) > 4096 for key in data):
        raise WireLimitError("DataBin fields exceed codec capacity")


def shape_tuple(shape):
    if type(shape) is not list:
        raise WireError("Expected DataBin shape list")
    if len(shape) > 16:
        raise WireLimitError("DataBin rank exceeds codec capacity")
    dims = tuple(integer(size, MAX_BYTES) for size in shape)
    if math.prod(dims) > MAX_BYTES:
        raise WireLimitError("DataBin shape exceeds codec capacity")
    return dims


def encode_primitive(item, depth):
    from qiskit.primitives import BitArray, DataBin, PrimitiveResult, PubResult, SamplerPubResult

    try:
        from .value_wire import encode
    except ImportError:
        from value_wire import encode
    if type(item) is BitArray:
        integer(item.num_bits, MAX_BYTES * 8)
        if item.array.nbytes > MAX_BYTES:
            raise WireLimitError("BitArray exceeds numeric byte capacity")
        return {
            "kind": "bit_array_v1",
            "array": array_record(item.array),
            "num_bits": item.num_bits,
        }
    if type(item) is DataBin:
        data = dict(item.items())
        data_fields(data)
        if any(getattr(item, key, None) is not value for key, value in data.items()):
            raise WireError("DataBin attributes and mapping diverge; alias semantics required")
        shape = list(item.shape)
        shape_tuple(shape)
        return {"kind": "data_bin_v1", "shape": shape, "data": encode(data, depth + 1)}
    if type(item) in (PrimitiveResult, PubResult, SamplerPubResult):
        if type(item.metadata) is not dict:
            raise WireError("Primitive metadata requires a dictionary")
        metadata = encode(item.metadata, depth + 1)
        if type(item) is PrimitiveResult:
            return {
                "kind": "primitive_result_v1",
                "metadata": metadata,
                "pubs": encode(list(item), depth + 1),
            }
        if type(item.data) is not DataBin:
            raise WireError("Pub result requires a DataBin")
        return {
            "kind": "sampler_pub_result_v1" if type(item) is SamplerPubResult else "pub_result_v1",
            "metadata": metadata,
            "data": encode(item.data, depth + 1),
        }
    return None


def decode_primitive(value, depth, budget):
    import numpy as np
    from qiskit.primitives import BitArray, DataBin, PrimitiveResult, PubResult, SamplerPubResult

    try:
        from .value_wire import decode
    except ImportError:
        from value_wire import decode
    kind = value["kind"]
    if kind == "bit_array_v1":
        fields(value, {"kind", "array", "num_bits"})
        bits = integer(value["num_bits"], MAX_BYTES * 8)
        array = decode_array(value["array"])
        if (
            type(array) is not np.ndarray
            or array.dtype != np.uint8
            or array.ndim < 2
            or array.shape[-1] != (bits + 7) // 8
        ):
            raise WireError("BitArray packed shape or dtype mismatch")
        return BitArray(array, bits)
    if kind == "data_bin_v1":
        fields(value, {"kind", "shape", "data"})
        shape = shape_tuple(value["shape"])
        data = decode(value["data"], depth + 1, budget)
        data_fields(data)
        try:
            return DataBin(shape=shape, **data)
        except (TypeError, ValueError) as exc:
            raise WireError("DataBin fields do not match shape") from exc
    if kind not in ("primitive_result_v1", "pub_result_v1", "sampler_pub_result_v1"):
        raise WireError("Unknown primitive result constructor")
    key = "pubs" if kind == "primitive_result_v1" else "data"
    fields(value, {"kind", "metadata", key})
    metadata = decode(value["metadata"], depth + 1, budget)
    if type(metadata) is not dict:
        raise WireError("Primitive metadata requires a dictionary")
    data = decode(value[key], depth + 1, budget)
    if kind == "primitive_result_v1":
        if type(data) is not list:
            raise WireError("Expected ordered primitive result list")
        return PrimitiveResult(data, metadata)
    if type(data) is not DataBin:
        raise WireError("Pub result requires a DataBin")
    cls = SamplerPubResult if kind == "sampler_pub_result_v1" else PubResult
    return cls(data, metadata)

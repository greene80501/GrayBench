"""Shared bounded value codec used on both sides of the candidate boundary."""

import math

try:  # Worker files are copied without installing the host orchestration package.
    from .circuit_wire import WireError, decode_circuit, encode_circuit
except ImportError:
    from circuit_wire import WireError, decode_circuit, encode_circuit

try:
    from .scientific_wire import decode_scientific, encode_scientific
except ImportError:
    from scientific_wire import decode_scientific, encode_scientific


def encode(item, depth=0):
    if depth > 32:
        raise WireError("Result nesting exceeds wire limit")
    if item is None or type(item) in (bool, str, int):
        return item
    if type(item) is float and math.isfinite(item):
        return item
    if type(item) is complex:
        if not math.isfinite(item.real) or not math.isfinite(item.imag):
            raise WireError("Non-finite Python complex scalar")
        return {"kind": "complex_v1", "real": item.real, "imag": item.imag}
    if type(item) in (list, tuple):
        return {"kind": type(item).__name__, "items": [encode(x, depth + 1) for x in item]}
    if type(item) is dict:
        return {
            "kind": "dict",
            "items": [[encode(k, depth + 1), encode(v, depth + 1)] for k, v in item.items()],
        }
    from qiskit import QuantumCircuit

    if isinstance(item, QuantumCircuit):
        return encode_circuit(item)
    scientific = encode_scientific(item)
    if scientific is not None:
        return scientific
    raise WireError("Unsupported wire value: " + type(item).__name__)


def decode(value, depth=0, budget=None):
    if budget is None:
        budget = [100_000]
    budget[0] -= 1
    if depth > 32 or budget[0] < 0:
        raise WireError("Result exceeds structural limit")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is dict and value.get("kind") == "complex_v1":
        if set(value) != {"kind", "real", "imag"} or any(
            type(value[k]) is not float or not math.isfinite(value[k]) for k in ("real", "imag")
        ):
            raise WireError("Invalid complex scalar")
        return complex(value["real"], value["imag"])
    if type(value) is dict and value.get("kind") in {
        "ndarray_v1",
        "numpy_scalar_v1",
        "statevector_v1",
        "densitymatrix_v1",
        "operator_v1",
    }:
        return decode_scientific(value)
    if type(value) is dict and value.get("kind") == "numeric_circuit_v1":
        return decode_circuit(value)
    if type(value) is not dict or set(value) != {"kind", "items"}:
        raise WireError("Invalid result wire type")
    if type(value["items"]) is not list:
        raise WireError("Invalid result items")
    if value["kind"] in ("list", "tuple"):
        items = [decode(x, depth + 1, budget) for x in value["items"]]
        return items if value["kind"] == "list" else tuple(items)
    if value["kind"] == "dict":
        result = {}
        for pair in value["items"]:
            if type(pair) is not list or len(pair) != 2:
                raise WireError("Invalid dictionary pair")
            key = decode(pair[0], depth + 1, budget)
            try:
                if key in result:
                    raise WireError("Duplicate dictionary key")
                result[key] = decode(pair[1], depth + 1, budget)
            except TypeError as exc:
                raise WireError("Unhashable dictionary key") from exc
        return result
    raise WireError("Unknown result kind")

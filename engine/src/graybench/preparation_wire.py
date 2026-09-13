"""Pinned StatePreparation representation, preserving original and current parameters.

Only bounded flat scalar collections, arrays and statevectors are admitted. No candidate
type name selects a constructor. Normalization is never performed during reconstruction.
"""

try:
    from .circuit_wire import WireError, fields, integer
except ImportError:
    from circuit_wire import WireError, fields, integer


def encode_preparation(op):
    try:
        from .value_wire import encode
    except ImportError:
        from value_wire import encode
    return {
        "kind": "state_preparation_v1",
        "original": encode(op._params_arg),
        "params": encode(op.params),
        "from_label": op._from_label,
        "from_int": op._from_int,
        "inverse": op._inverse,
    }


def flat_value(wire, depth=0):
    try:
        from .value_wire import decode
    except ImportError:
        from value_wire import decode

    def scalar(item):
        import numpy as np

        if isinstance(item, np.number):
            scalar(item.item())
            return item
        if type(item) in (int, float, str, complex):
            if type(item) is str and (len(item) > 15 or any(c not in "01+-lr" for c in item)):
                raise WireError("Invalid preparation label")
            if type(item) is int and item.bit_length() > 64:
                raise WireError("Preparation integer exceeds limit")
            return item
        raise WireError("Invalid preparation scalar")

    if type(wire) is dict and wire.get("kind") in ("list", "tuple"):
        if depth:
            raise WireError("Nested preparation collections are unsupported")
        fields(wire, {"kind", "items"})
        if type(wire["items"]) is not list or len(wire["items"]) > 32768:
            raise WireError("Preparation vector exceeds limit")
        items = [flat_value(v, depth + 1) for v in wire["items"]]
        for item in items:
            scalar(item)
        return items if wire["kind"] == "list" else tuple(items)
    if type(wire) is dict:
        if depth and wire.get("kind") in ("ndarray_v1", "statevector_v1"):
            raise WireError("Nested preparation arrays are unsupported")
        if wire.get("kind") not in (
            "complex_v1",
            "numpy_scalar_v1",
            "ndarray_v1",
            "statevector_v1",
        ):
            raise WireError("Unsupported preparation value")
        item = decode(wire)
        import numpy as np
        from qiskit.quantum_info import Statevector

        if isinstance(item, Statevector):
            if item.data.ndim != 1 or item.data.size > 32768:
                raise WireError("Preparation state exceeds limit")
        elif isinstance(item, np.ndarray):
            if item.ndim != 1 or item.size > 32768:
                raise WireError("Preparation array exceeds limit")
        elif isinstance(item, np.number):
            scalar(item.item())
        else:
            scalar(item)
        return item
    return scalar(decode(wire))


def decode_preparation(wire, qubits, name):
    fields(wire, {"kind", "original", "params", "from_label", "from_int", "inverse"})
    if wire["kind"] != "state_preparation_v1" or not 1 <= integer(qubits, 15) <= 15:
        raise WireError("Invalid preparation dimensions")
    if any(type(wire[k]) is not bool for k in ("from_label", "from_int", "inverse")):
        raise WireError("Invalid preparation flags")
    if name != ("state_preparation_dg" if wire["inverse"] else "state_preparation"):
        raise WireError("Preparation inverse/name mismatch")
    original, params = flat_value(wire["original"]), flat_value(wire["params"])
    if type(params) is not list:
        raise WireError("Invalid stored preparation parameters")
    if wire["from_label"] != isinstance(original, str) or wire["from_int"] != isinstance(
        original, int
    ):
        raise WireError("Preparation mode mismatch")
    from qiskit.circuit.library import StatePreparation

    # A constant-size constructor establishes the pinned SDK object's invariants. Restore
    # stored parameters separately: using the original constructor argument would normalize
    # again or reject a deliberately modified value, and would change inverse() behavior.
    op = StatePreparation(0, num_qubits=qubits, inverse=wire["inverse"])
    op._params_arg = original
    op._from_label, op._from_int = wire["from_label"], wire["from_int"]
    op.params = params
    return op

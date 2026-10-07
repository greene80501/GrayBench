"""Fixed ScalarOp/SparsePauliOp constructors; no term simplification or dense expansion."""

try:
    from .circuit_wire import WireError, WireLimitError, fields
    from .scientific_wire import array_record, decode_array, dimensions
    from .symbolic_wire import decode_parameter, encode_parameter
except ImportError:
    from circuit_wire import WireError, WireLimitError, fields
    from scientific_wire import array_record, decode_array, dimensions
    from symbolic_wire import decode_parameter, encode_parameter


def shape_record(item):
    incoming, outgoing = list(item.input_dims()), list(item.output_dims())
    dimensions(incoming)
    dimensions(outgoing)
    qargs = None if item.qargs is None else list(item.qargs)
    if qargs is not None and any(type(q) is not int or q < 0 for q in qargs):
        raise WireError("Unsupported bound operator arguments")
    return {"input_dims": incoming, "output_dims": outgoing, "qargs": qargs}


def encode_operator(item):
    import numpy as np
    from qiskit.quantum_info import ScalarOp

    shape = shape_record(item)
    if type(item) is ScalarOp:
        try:
            from .value_wire import encode
        except ImportError:
            from value_wire import encode
        return {"kind": "scalar_op_v1", "coefficient": encode(item.coeff), **shape}
    coefficients = item.coeffs
    if coefficients.dtype == object:
        if coefficients.size > 16384:
            raise WireLimitError("Symbolic coefficient count exceeds codec limit")
        coeffs = {
            "kind": "symbolic_coefficients_v1",
            "items": [encode_parameter(c) for c in coefficients],
        }
    elif coefficients.dtype == np.dtype(complex):
        coeffs = array_record(coefficients)
    else:
        raise WireError("Unsupported sparse coefficient dtype")
    return {
        "kind": "sparse_pauli_op_v1",
        "z": array_record(item.paulis.z),
        "x": array_record(item.paulis.x),
        "phase": array_record(item.paulis.phase),
        "coefficients": coeffs,
        **shape,
    }


def decode_operator(value):
    import math
    from numbers import Number

    import numpy as np
    from qiskit.quantum_info import PauliList, ScalarOp, SparsePauliOp

    scalar = value.get("kind") == "scalar_op_v1"
    fields(
        value,
        {"kind", "coefficient" if scalar else "coefficients", "input_dims", "output_dims", "qargs"}
        | (set() if scalar else {"z", "x", "phase"}),
    )
    incoming, outgoing = dimensions(value["input_dims"]), dimensions(value["output_dims"])
    qargs = value["qargs"]
    if qargs is not None and (
        type(qargs) is not list
        or len(qargs) not in (len(incoming), len(outgoing))
        or any(type(q) is not int or q < 0 for q in qargs)
    ):
        raise WireError("Invalid bound operator arguments")
    if scalar:
        coeff = value["coefficient"]
        if not (
            type(coeff) in (bool, int, float)
            or type(coeff) is dict
            and coeff.get("kind") in ("complex_v1", "numpy_scalar_v1")
        ):
            raise WireError("Invalid scalar coefficient representation")
        try:
            from .value_wire import decode
        except ImportError:
            from value_wire import decode
        coeff = decode(coeff)
        if not isinstance(coeff, Number) or math.prod(incoming) != math.prod(outgoing):
            raise WireError("Invalid scalar coefficient or dimensions")
        result = ScalarOp(incoming, coeff=coeff)
    else:
        if value["kind"] != "sparse_pauli_op_v1":
            raise WireError("Unknown sparse operator codec")
        z, x, phase = (decode_array(value[key]) for key in ("z", "x", "phase"))
        if (
            z.dtype.kind != "b"
            or x.dtype.kind != "b"
            or z.ndim != 2
            or x.shape != z.shape
            or phase.dtype.kind not in "iu"
            or phase.shape != (z.shape[0],)
            or np.any(phase > 3)
            or np.any(phase < 0)
        ):
            raise WireError("Invalid Pauli symplectic arrays")
        if z.shape[1] > 512:
            raise WireLimitError("Pauli qubit count exceeds codec limit")
        if math.prod(incoming) != 2 ** z.shape[1] or math.prod(outgoing) != 2 ** z.shape[1]:
            raise WireError("Sparse operator dimensions differ from Pauli width")
        record = value["coefficients"]
        if type(record) is dict and record.get("kind") == "symbolic_coefficients_v1":
            fields(record, {"kind", "items"})
            if type(record["items"]) is not list or len(record["items"]) != z.shape[0]:
                raise WireError("Invalid symbolic coefficient list")
            if len(record["items"]) > 16384:
                raise WireLimitError("Symbolic coefficient count exceeds codec limit")
            context, budget = {"parameters": {}, "vectors": {}}, [100000]
            coeffs = np.array(
                [decode_parameter(c, context, budget=budget) for c in record["items"]], dtype=object
            )
        else:
            coeffs = decode_array(record)
            if coeffs.dtype != np.dtype(complex):
                raise WireError("Invalid numeric sparse coefficient dtype")
        if coeffs.shape != (z.shape[0],):
            raise WireError("Sparse coefficient count differs from Pauli terms")
        paulis = PauliList.from_symplectic(z, x, phase)
        result = SparsePauliOp(paulis, coeffs, ignore_pauli_phase=True, copy=False)
    result = result.reshape(input_dims=incoming, output_dims=outgoing)
    return result if qargs is None else result(qargs)

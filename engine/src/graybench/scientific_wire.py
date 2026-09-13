"""Data-only numeric arrays and quantum states/operators with bounded allocations.

Numeric bytes preserve dtype, endianness, complex values, signed zero and non-finite values.
Object/string/structured dtypes are never accepted. Invalid physical states remain candidate
values to be judged; the codec does not silently normalize or repair them.
"""

import base64
import math

try:
    from .circuit_wire import WireError, fields
except ImportError:
    from circuit_wire import WireError, fields

MAX_BYTES = 512 * 1024
DTYPES = {"|b1", "|i1", "|u1"} | {
    endian + kind + str(size)
    for endian in ("<", ">")
    for kind, sizes in (("i", (2, 4, 8)), ("u", (2, 4, 8)), ("f", (2, 4, 8)), ("c", (8, 16)))
    for size in sizes
}


def array_record(array, *, scalar=False):
    if array.dtype.str not in DTYPES or array.nbytes > MAX_BYTES or array.ndim > 16:
        raise WireError("Unsupported or oversized numeric array")
    return {
        "kind": "numpy_scalar_v1" if scalar else "ndarray_v1",
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "bytes": base64.b64encode(array.tobytes(order="C")).decode("ascii"),
    }


def decode_array(value):
    import numpy as np

    fields(value, {"kind", "dtype", "shape", "bytes"})
    if value["kind"] not in {"ndarray_v1", "numpy_scalar_v1"}:
        raise WireError("Unknown numeric value kind")
    if type(value["dtype"]) is not str or value["dtype"] not in DTYPES:
        raise WireError("Unsafe or unsupported numeric dtype")
    shape = value["shape"]
    if type(shape) is not list or len(shape) > 16:
        raise WireError("Invalid array rank")
    if any(type(d) is not int or not 0 <= d <= MAX_BYTES for d in shape):
        raise WireError("Invalid array dimension")
    if value["kind"] == "numpy_scalar_v1" and shape:
        raise WireError("Scalar cannot have nonzero rank")
    dtype = np.dtype(value["dtype"])
    expected = math.prod(shape) * dtype.itemsize
    if expected > MAX_BYTES:
        raise WireError("Array allocation exceeds limit")
    text = value["bytes"]
    if type(text) is not str or len(text) != 4 * ((expected + 2) // 3):
        raise WireError("Numeric byte length mismatch")
    try:
        data = base64.b64decode(text, validate=True)
    except ValueError as exc:
        raise WireError("Invalid numeric byte encoding") from exc
    if len(data) != expected:
        raise WireError("Numeric byte length mismatch")
    # Copy creates a writable value independent of the transport's immutable bytes.
    array = np.frombuffer(data, dtype=dtype).reshape(tuple(shape)).copy()
    return array[()] if value["kind"] == "numpy_scalar_v1" else array


def encode_scientific(item):
    import numpy as np
    from qiskit.quantum_info import (
        Choi,
        Clifford,
        DensityMatrix,
        Operator,
        StabilizerState,
        Statevector,
    )

    if type(item) is np.ndarray:
        return array_record(item)
    if isinstance(item, np.generic):
        return array_record(np.asarray(item), scalar=True)
    for tag, cls in (("statevector_v1", Statevector), ("densitymatrix_v1", DensityMatrix)):
        if type(item) is cls:
            return {"kind": tag, "data": array_record(item.data), "dims": list(item.dims())}
    if type(item) in (Clifford, StabilizerState):
        if (
            getattr(item, "qargs", None) is not None
            or getattr(item, "_rng_generator", None) is not None
        ):
            raise WireError("Bound subsystem or RNG state requires an explicit codec")
        tableau = item.tableau if type(item) is Clifford else item.clifford.tableau
        return {
            "kind": "clifford_v1" if type(item) is Clifford else "stabilizer_v1",
            "tableau": array_record(tableau),
        }
    if type(item) in (Operator, Choi):
        if type(item) is Choi and item.qargs is not None:
            raise WireError("Bound channel subsystems require an explicit codec")
        return {
            "kind": "operator_v1" if type(item) is Operator else "choi_v1",
            "data": array_record(item.data),
            "input_dims": list(item.input_dims()),
            "output_dims": list(item.output_dims()),
        }
    return None


def dimensions(value):
    if (
        type(value) is not list
        or len(value) > 32
        or any(type(d) is not int or not 1 <= d <= MAX_BYTES for d in value)
    ):
        raise WireError("Invalid quantum subsystem dimensions")
    if math.prod(value) > MAX_BYTES:
        raise WireError("Quantum dimension exceeds limit")
    return tuple(value)


def decode_scientific(value):
    if value.get("kind") in {"ndarray_v1", "numpy_scalar_v1"}:
        return decode_array(value)
    from qiskit.quantum_info import (
        Choi,
        Clifford,
        DensityMatrix,
        Operator,
        StabilizerState,
        Statevector,
    )

    kind = value.get("kind")
    if kind in ("clifford_v1", "stabilizer_v1"):
        fields(value, {"kind", "tableau"})
        tableau = decode_array(value["tableau"])
        if (
            tableau.dtype.kind != "b"
            or tableau.ndim != 2
            or tableau.shape[0] % 2
            or not 2 <= tableau.shape[0] <= 512
            or tableau.shape[1] != tableau.shape[0] + 1
        ):
            raise WireError("Invalid Clifford tableau shape or dtype")
        # Preserve even invalid symplectic values produced with SDK validation disabled.
        clifford = Clifford(tableau, validate=False)
        return clifford if kind == "clifford_v1" else StabilizerState(clifford, validate=False)
    if kind in ("operator_v1", "choi_v1"):
        fields(value, {"kind", "data", "input_dims", "output_dims"})
        incoming, outgoing = dimensions(value["input_dims"]), dimensions(value["output_dims"])
        array = decode_array(value["data"])
        expected = (math.prod(outgoing), math.prod(incoming))
        if kind == "choi_v1":
            expected = (math.prod(outgoing) * math.prod(incoming),) * 2
        if array.shape != expected:
            raise WireError("Operator shape does not match subsystem dimensions")
        cls = Operator if kind == "operator_v1" else Choi
        return cls(array, input_dims=incoming, output_dims=outgoing)
    fields(value, {"kind", "data", "dims"})
    dims = dimensions(value["dims"])
    array = decode_array(value["data"])
    dimension = math.prod(dims)
    if kind == "statevector_v1" and array.shape == (dimension,):
        return Statevector(array, dims=dims)
    if kind == "densitymatrix_v1" and array.shape == (dimension, dimension):
        return DensityMatrix(array, dims=dims)
    raise WireError("Quantum value shape does not match its declared type")

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


def dihedral_shapes(n):
    if type(n) is not int or not 1 <= n <= 64:
        raise WireError("Unsupported CNOTDihedral qubit count")
    return {
        "linear": (n, n),
        "shift": (n,),
        "weight_1": (n,),
        "weight_2": (math.comb(n, 2),),
        "weight_3": (math.comb(n, 3),),
    }


def encode_dihedral(item):
    import numpy as np
    from qiskit.quantum_info.operators.dihedral.polynomial import SpecialPolynomial

    n = item.num_qubits
    shapes = dihedral_shapes(n)
    if (
        set(vars(item)) != {"_num_qubits", "poly", "linear", "shift", "_qargs", "_op_shape"}
        or type(item._num_qubits) is not int
        or item._num_qubits != n
        or item.qargs is not None
        or item.input_dims() != (2,) * n
        or item.output_dims() != (2,) * n
    ):
        raise WireError("Unsupported CNOTDihedral object state")
    poly = item.poly
    if (
        type(poly) is not SpecialPolynomial
        or set(vars(poly))
        != {"n_vars", "nc2", "nc3", "weight_0", "weight_1", "weight_2", "weight_3"}
        or any(type(x) is not int for x in (poly.n_vars, poly.nc2, poly.nc3))
        or (poly.n_vars, poly.nc2, poly.nc3) != (n, math.comb(n, 2), math.comb(n, 3))
    ):
        raise WireError("Unsupported CNOTDihedral polynomial state")
    result = {"kind": "cnot_dihedral_v1", "qubits": n}
    if type(poly.weight_0) is int:
        result["weight_0"] = poly.weight_0
    elif isinstance(poly.weight_0, np.integer):
        result["weight_0"] = array_record(np.asarray(poly.weight_0), scalar=True)
    else:
        raise WireError("Unsupported CNOTDihedral constant coefficient")
    for name, shape in shapes.items():
        array = getattr(item if name in ("linear", "shift") else poly, name)
        if name == "shift" and type(array) is list and len(array) == n:
            entries = []
            for scalar in array:
                if type(scalar) is int:
                    entries.append(scalar)
                elif isinstance(scalar, np.integer):
                    entries.append(array_record(np.asarray(scalar), scalar=True))
                else:
                    raise WireError("Unsupported CNOTDihedral list shift value")
            result[name] = {"kind": "integer_list_v1", "items": entries}
            continue
        if type(array) is not np.ndarray or array.shape != shape:
            raise WireError("Unsupported CNOTDihedral array shape")
        result[name] = array_record(array)
    return result


def decode_dihedral(value):
    import numpy as np
    from qiskit.quantum_info import CNOTDihedral

    fields(
        value, {"kind", "qubits", "linear", "shift", "weight_0", "weight_1", "weight_2", "weight_3"}
    )
    shapes = dihedral_shapes(value["qubits"])
    arrays = {}
    for name, shape in shapes.items():
        record = value[name]
        if name == "shift" and type(record) is dict and record.get("kind") == "integer_list_v1":
            fields(record, {"kind", "items"})
            if type(record["items"]) is not list or len(record["items"]) != value["qubits"]:
                raise WireError("Invalid CNOTDihedral list shift shape")
            entries = []
            for scalar in record["items"]:
                if type(scalar) is not int:
                    scalar = decode_array(scalar)
                    if not isinstance(scalar, np.integer):
                        raise WireError("Invalid CNOTDihedral list shift value")
                entries.append(scalar)
            arrays[name] = entries
            continue
        array = decode_array(value[name])
        if type(array) is not np.ndarray or array.shape != shape:
            raise WireError("Invalid CNOTDihedral array shape")
        arrays[name] = array
    constant = value["weight_0"]
    if type(constant) is not int:
        constant = decode_array(constant)
        if not isinstance(constant, np.integer):
            raise WireError("Invalid CNOTDihedral constant coefficient")
    result = CNOTDihedral(num_qubits=value["qubits"], validate=False)
    # Preserve invalid numeric values for the oracle; do not reduce coefficients or repair matrices.
    result.poly.weight_0 = constant
    for name, array in arrays.items():
        setattr(result if name in ("linear", "shift") else result.poly, name, array)
    return result


def encode_statevector(item):
    """Read exact Qiskit instance state, not candidate-patchable public accessors."""
    import numpy as np
    from qiskit.quantum_info.operators.op_shape import OpShape

    state = object.__getattribute__(item, "__dict__")
    data, shape = state.get("_data"), state.get("_op_shape")
    if type(data) is not np.ndarray or type(shape) is not OpShape:
        raise WireError("Unsupported Statevector instance state")
    raw = object.__getattribute__(shape, "__dict__")
    if set(raw) != {"_num_qargs_l", "_num_qargs_r", "_dims_l", "_dims_r"}:
        raise WireError("Unsupported Statevector subsystem state")
    count, right, left_dims, right_dims = (
        raw["_num_qargs_l"],
        raw["_num_qargs_r"],
        raw["_dims_l"],
        raw["_dims_r"],
    )
    if (
        type(count) is not int
        or not 0 <= count <= 32
        or type(right) is not int
        or right != 0
        or right_dims is not None
        or (left_dims is not None and type(left_dims) is not tuple)
    ):
        raise WireError("Invalid Statevector subsystem state")
    dims = (2,) * count if left_dims is None else left_dims
    if (
        len(dims) != count
        or any(type(d) is not int or not 1 <= d <= MAX_BYTES for d in dims)
        or math.prod(dims) > MAX_BYTES
        or data.shape != (math.prod(dims),)
    ):
        raise WireError("Statevector data and subsystem dimensions differ")
    return {"kind": "statevector_v1", "data": array_record(data), "dims": list(dims)}


def encode_scientific(item):
    import numpy as np
    from qiskit.quantum_info import (
        Choi,
        Clifford,
        CNOTDihedral,
        DensityMatrix,
        Operator,
        ScalarOp,
        SparsePauliOp,
        StabilizerState,
        Statevector,
    )

    if type(item) is CNOTDihedral:
        return encode_dihedral(item)
    if type(item) in (ScalarOp, SparsePauliOp):
        try:
            from .operator_wire import encode_operator
        except ImportError:
            from operator_wire import encode_operator
        return encode_operator(item)
    if type(item) is np.ndarray:
        return array_record(item)
    if isinstance(item, np.generic):
        return array_record(np.asarray(item), scalar=True)
    if type(item) is Statevector:
        return encode_statevector(item)
    if type(item) is DensityMatrix:
        return {
            "kind": "densitymatrix_v1",
            "data": array_record(item.data),
            "dims": list(item.dims()),
        }
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
    if value.get("kind") in ("scalar_op_v1", "sparse_pauli_op_v1"):
        try:
            from .operator_wire import decode_operator
        except ImportError:
            from operator_wire import decode_operator
        return decode_operator(value)
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

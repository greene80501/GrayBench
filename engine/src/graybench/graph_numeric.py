"""Numeric graph nodes with shared ndarray ownership and bounded view geometry.

Only exact ndarrays backed by an exact owning ndarray are admitted. External
buffer owners and changes to an exported array's geometry require further codecs;
neither falls back to independent value copies.
"""

import base64
import math
from dataclasses import dataclass

from graybench.circuit_wire import WireError, WireLimitError, fields
from graybench.scientific_wire import DTYPES, MAX_BYTES, array_record


def numeric_dtype(state):
    import numpy as np

    if type(state["dtype"]) is not str or state["dtype"] not in DTYPES:
        raise WireError("Unsupported graph array dtype")
    char = state["dtype_char"]
    if type(char) is not str or char not in tuple("?bBhHiIlLqQefdFD"):
        raise WireError("Unsupported graph numeric C type")
    dtype = np.dtype(char).newbyteorder(state["dtype"][0])
    if dtype.str != state["dtype"]:
        raise WireError("Numeric C type differs from declared storage dtype")
    return dtype


def geometry(state):
    dtype = numeric_dtype(state)
    shape, strides = state["shape"], state["strides"]
    if (
        type(shape) is not list
        or len(shape) > 16
        or any(type(n) is not int or not 0 <= n <= MAX_BYTES for n in shape)
        or type(strides) is not list
        or len(strides) != len(shape)
        or any(type(n) is not int or abs(n) > MAX_BYTES for n in strides)
        or type(state["writeable"]) is not bool
        or type(state["aligned"]) is not bool
    ):
        raise WireError("Invalid graph array geometry")
    if math.prod(max(1, n) for n in shape) * dtype.itemsize > MAX_BYTES:
        raise WireLimitError("Graph array logical extent exceeds limit")
    return dtype, math.prod(shape) * dtype.itemsize


def bounds(state, capacity, offset):
    dtype, size = geometry(state)
    if type(offset) is not int or not 0 <= offset <= capacity:
        raise WireError("Invalid graph array offset")
    low = high = offset
    if size:
        for length, stride in zip(state["shape"], state["strides"], strict=True):
            delta = (length - 1) * stride
            low += min(delta, 0)
            high += max(delta, 0)
        if low < 0 or high + dtype.itemsize > capacity:
            raise WireError("Graph array view exceeds its storage")
        if state["aligned"] and (
            offset % dtype.alignment
            or any(
                length > 1 and stride % dtype.alignment
                for length, stride in zip(state["shape"], state["strides"], strict=True)
            )
        ):
            raise WireError("Graph array alignment flag contradicts its geometry")


def owner_order(state):
    dtype, size = geometry(state)
    for order in ("C", "F"):
        axes = range(len(state["shape"]))
        expected = dtype.itemsize
        valid = True
        for axis in reversed(axes) if order == "C" else axes:
            n = state["shape"][axis]
            if n > 1 and state["strides"][axis] != expected:
                valid = False
            expected *= max(1, n)
        if valid or not size:
            return order
    raise WireError("Noncontiguous owning array requires a graph codec")


def payload(state):
    _, size = geometry(state)
    encoded = state["bytes"]
    if type(encoded) is not str or len(encoded) != 4 * ((size + 2) // 3):
        raise WireError("Graph numeric byte length mismatch")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise WireError("Invalid graph numeric bytes") from exc
    if len(data) != size or base64.b64encode(data).decode("ascii") != encoded:
        raise WireError("Noncanonical graph numeric bytes")
    return data


@dataclass(frozen=True)
class ArrayUpdate:
    data: bytes | None
    writeable: bool
    aligned: bool


@dataclass(frozen=True)
class ArrayCodec:
    kind: str
    immutable: bool = False

    def matrix_refs(self, state):
        return ()

    def matches(self, value):
        import numpy as np

        return type(value) is np.ndarray and (value.base is None) == (self.kind == "ndarray_owner")

    def state(self, value, ref):
        import numpy as np

        result = {
            "dtype": value.dtype.str,
            "dtype_char": value.dtype.char,
            "shape": list(value.shape),
            "strides": list(value.strides),
            "writeable": bool(value.flags.writeable),
            "aligned": bool(value.flags.aligned),
        }
        if value.dtype.metadata is not None:
            raise WireError("Numeric dtype metadata requires a graph codec")
        if value.flags.writebackifcopy:
            raise WireError("Write-back array storage requires a graph codec")
        geometry(result)
        if self.kind == "ndarray_owner":
            if not value.flags.owndata or not (
                value.flags.c_contiguous or value.flags.f_contiguous
            ):
                raise WireError("Unsupported owning graph array storage")
            result["bytes"] = base64.b64encode(value.tobytes(order="A")).decode("ascii")
        else:
            base = value.base
            if type(base) is not np.ndarray or base.base is not None or not base.flags.owndata:
                raise WireError("External array buffer requires a graph codec")
            result["base"] = ref(base)
            result["offset"] = (
                value.__array_interface__["data"][0] - base.__array_interface__["data"][0]
            )
            bounds(result, base.nbytes, result["offset"])
        return result

    def validate(self, state, shape_index):
        expected = {"dtype", "dtype_char", "shape", "strides", "writeable", "aligned"}
        fields(
            state, expected | ({"bytes"} if self.kind == "ndarray_owner" else {"base", "offset"})
        )
        _, size = geometry(state)
        if self.kind == "ndarray_owner":
            owner_order(state)
            bounds(state, size, 0)
            payload(state)
        else:
            token = state["base"]
            if type(token) is not dict or set(token) != {"ref"} or type(token["ref"]) is not str:
                raise WireError("Invalid graph array base reference")
            base = shape_index.get(token["ref"])
            if base is None or base["kind"] != "ndarray_owner":
                raise WireError("Graph array base must be an owning array")
            # The target may occur later in the message. Validate its structure now.
            fields(base["state"], expected | {"bytes"})
            _, capacity = geometry(base["state"])
            bounds(state, capacity, state["offset"])

    def validate_update(self, previous, state):
        stable = {"dtype", "dtype_char", "shape", "strides"}
        if self.kind == "ndarray_view":
            stable |= {"base", "offset"}
        if any(previous[key] != state[key] for key in stable):
            raise WireError("Exported array geometry changes require a graph codec")

    def array_bytes(self, state):
        return geometry(state)[1] if self.kind == "ndarray_owner" else 0

    def tokens(self, state):
        return () if self.kind == "ndarray_owner" else (state["base"],)

    def allocate(self, state, shape_index):
        import numpy as np

        if self.kind == "ndarray_view":
            return None
        value = np.zeros(
            tuple(state["shape"]), dtype=numeric_dtype(state), order=owner_order(state)
        )
        value.strides = tuple(state["strides"])
        return value

    def populate(self, target, state, resolve):
        import numpy as np

        if self.kind == "ndarray_view":
            return np.ndarray(
                tuple(state["shape"]),
                dtype=numeric_dtype(state),
                buffer=resolve(state["base"]["ref"]),
                offset=state["offset"],
                strides=tuple(state["strides"]),
            )
        return target

    def prepare(self, state, resolve, shape_index):
        return ArrayUpdate(
            payload(state) if self.kind == "ndarray_owner" else None,
            state["writeable"],
            state["aligned"],
        )

    def apply(self, target, prepared):
        import numpy as np

        if prepared.data is not None:
            target.flags.writeable = True
            raw = np.ndarray((len(prepared.data),), dtype=np.uint8, buffer=target)
            raw[:] = np.frombuffer(prepared.data, dtype=np.uint8)
            target.flags.writeable = prepared.writeable
        elif target.flags.writeable != prepared.writeable:
            # A view can remain writable after its owning array was made readonly.
            # Restore that valid relation without leaving the owner writable.
            owner = target.base
            original_flag = owner.flags.writeable
            try:
                if prepared.writeable:
                    owner.flags.writeable = True
                target.flags.writeable = prepared.writeable
            finally:
                owner.flags.writeable = original_flag
        target.flags.aligned = prepared.aligned


ARRAY_CODECS = {kind: ArrayCodec(kind) for kind in ("ndarray_owner", "ndarray_view")}


@dataclass(frozen=True)
class NumpyScalarCodec:
    kind: str = "numpy_scalar"
    immutable: bool = True

    def matrix_refs(self, state):
        return ()

    def matches(self, value):
        import numpy as np

        return (
            isinstance(value, np.generic)
            and value.dtype.str in DTYPES
            and type(value) is value.dtype.type
        )

    def state(self, value, ref):
        import numpy as np

        state = array_record(np.asarray(value), scalar=True)
        state["dtype_char"] = value.dtype.char
        return state

    def validate(self, state, shape_index):
        fields(state, {"kind", "dtype", "dtype_char", "shape", "bytes"})
        if state["kind"] != "numpy_scalar_v1" or state["shape"] != []:
            raise WireError("Invalid graph numpy scalar")
        dtype = numeric_dtype(state)
        encoded = state["bytes"]
        if type(encoded) is not str or len(encoded) != 4 * ((dtype.itemsize + 2) // 3):
            raise WireError("Invalid graph scalar byte length")
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise WireError("Invalid graph scalar bytes") from exc
        if len(data) != dtype.itemsize:
            raise WireError("Invalid graph scalar byte length")
        value = self.allocate(state, shape_index)
        if value.dtype.str != state["dtype"] or value.tobytes() != data:
            raise WireError("Noncanonical graph numpy scalar")
        if base64.b64encode(value.tobytes()).decode("ascii") != state["bytes"]:
            raise WireError("Noncanonical graph numpy scalar bytes")

    def validate_update(self, previous, state):
        pass  # The arena compares exact canonical wire bytes for immutable nodes.

    def array_bytes(self, state):
        return numeric_dtype(state).itemsize

    def tokens(self, state):
        return ()

    def allocate(self, state, shape_index):
        import numpy as np

        return np.frombuffer(base64.b64decode(state["bytes"]), dtype=numeric_dtype(state))[0]


ARRAY_CODECS["numpy_scalar"] = NumpyScalarCodec()

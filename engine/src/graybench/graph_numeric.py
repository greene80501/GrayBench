"""Numeric graph nodes with shared ndarray ownership and bounded view geometry.

Only exact ndarrays backed by an exact owning ndarray are admitted. Geometry
updates preserve the existing storage byte count, base and data offset. External
buffers and storage resizing remain unsupported, without value-copy fallback.
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
    geometry: tuple | None = None


def apply_array_geometry(target, proposed):
    """Change metadata without replacing or reallocating the owning storage."""
    dtype, shape, strides = proposed
    if (
        target.dtype.str == dtype.str
        and target.dtype.char == dtype.char
        and target.shape == shape
        and target.strides == strides
    ):
        return
    old_size = target.size
    if target.base is None:
        # Owning arrays are validated contiguous. Never shrink their address span:
        # NumPy uses that span when checking later strides assignments.
        step = target.itemsize
        contiguous = []
        for n in reversed(target.shape):
            contiguous.append(step)
            step *= max(1, n)
        target.strides = tuple(reversed(contiguous))
        target.shape = (old_size,)
        if dtype.kind != "O":
            target.dtype = dtype
    else:
        target.strides = (0,) * target.ndim
        if dtype.kind != "O" and target.dtype.itemsize != dtype.itemsize:
            # A tiny contiguous final axis permits dtype reinterpretation even
            # when the outer layout has negative/zero strides. The native old and
            # validated new elements both fit at the unchanged data offset.
            width = math.lcm(target.itemsize, dtype.itemsize) // target.itemsize
            target.shape = (old_size // width, width) if old_size else (0,)
            target.strides = (0, target.itemsize) if old_size else (target.itemsize,)
            target.dtype = dtype
        elif dtype.kind != "O":
            target.dtype = dtype
        target.strides = (0,) * target.ndim
    target.shape = shape
    target.strides = strides


@dataclass(frozen=True)
class ArrayCodec:
    kind: str
    immutable: bool = False

    def matrix_refs(self, state):
        return ()

    def matches(self, value):
        import numpy as np

        return (
            type(value) is np.ndarray
            and value.dtype.kind != "O"
            and (value.base is None) == (self.kind == "ndarray_owner")
        )

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
            from graybench.graph_native import native_module, registered_native_root

            if type(base) is not np.ndarray or not (
                (base.base is None and base.flags.owndata) or registered_native_root(base)
            ):
                raise WireError("External array buffer requires a graph codec")
            result["base"] = ref(base)
            result["offset"] = (
                value.__array_interface__["data"][0] - base.__array_interface__["data"][0]
            )
            capacity = (
                native_module()._graybench_storage_info(base.base)[1]
                if registered_native_root(base)
                else base.nbytes
            )
            bounds(result, capacity, result["offset"])
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
            if base is None or base["kind"] not in ("ndarray_owner", "native_root"):
                raise WireError("Graph array base must be an owning array")
            # The target may occur later in the message. Validate its structure now.
            if base["kind"] == "native_root":
                from graybench.graph_native import native_capacity

                capsule_token = base["state"].get("base")
                if (
                    type(capsule_token) is not dict
                    or set(capsule_token) != {"ref"}
                    or type(capsule_token["ref"]) is not str
                ):
                    raise WireError("Registered view owner has no capsule reference")
                capsule = shape_index.get(capsule_token["ref"])
                if capsule is None or capsule["kind"] != "native_capsule":
                    raise WireError("Registered view owner has no native capsule")
                capacity = native_capacity(capsule["state"])
            else:
                fields(base["state"], expected | {"bytes"})
                _, capacity = geometry(base["state"])
            bounds(state, capacity, state["offset"])

    def validate_update(self, previous, state):
        if geometry(previous)[1] != geometry(state)[1]:
            raise WireError("Exported array storage resizing requires another graph codec")
        if self.kind == "ndarray_view" and any(previous[k] != state[k] for k in ("base", "offset")):
            raise WireError("Exported array base/offset changes require another graph codec")

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
            root = resolve(state["base"]["ref"])
            from graybench.graph_native import native_module, registered_native_root

            if registered_native_root(root):
                return native_module()._graybench_storage_view(
                    root,
                    numeric_dtype(state),
                    tuple(state["shape"]),
                    tuple(state["strides"]),
                    state["offset"],
                )
            return np.ndarray(
                tuple(state["shape"]),
                dtype=numeric_dtype(state),
                buffer=root,
                offset=state["offset"],
                strides=tuple(state["strides"]),
            )
        return target

    def prepare(self, state, resolve, shape_index):
        return ArrayUpdate(
            payload(state) if self.kind == "ndarray_owner" else None,
            state["writeable"],
            state["aligned"],
            (numeric_dtype(state), tuple(state["shape"]), tuple(state["strides"])),
        )

    def apply(self, target, prepared):
        import numpy as np

        if prepared.geometry is not None:
            apply_array_geometry(target, prepared.geometry)
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

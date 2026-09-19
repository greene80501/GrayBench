"""Object arrays as bounded reference slots, never raw NumPy pointer bytes."""

from dataclasses import dataclass

from graybench.circuit_wire import WireError, fields
from graybench.graph_numeric import (
    ArrayCodec,
    ArrayUpdate,
    apply_array_geometry,
    bounds,
    geometry,
    owner_order,
)

COMMON = {"shape", "strides", "writeable", "aligned", "itemsize"}


def slot_geometry(state):
    import numpy as np

    if (
        type(state["itemsize"]) is not int
        or state["itemsize"] != 8
        or np.dtype(object).itemsize != 8
    ):
        raise WireError("Object-reference arrays require the pinned 64-bit layout")
    proxy = dict(state, dtype="<u8", dtype_char="Q")
    _, size = geometry(proxy)
    if any(stride % 8 for stride in state["strides"]):
        raise WireError("Object-array strides must address complete reference slots")
    return proxy, size


def slot_bounds(state, capacity, offset):
    proxy, _ = slot_geometry(state)
    if type(offset) is not int or offset % 8:
        raise WireError("Object-array offset must address a complete reference slot")
    # Alignment must be safe even if the caller deliberately cleared the flag.
    bounds(dict(proxy, aligned=True), capacity, offset)


def base_record(state, index):
    token = state["base"]
    if type(token) is not dict or set(token) != {"ref"} or type(token["ref"]) is not str:
        raise WireError("Invalid object-array owner reference")
    base = index.get(token["ref"])
    if base is None or base["kind"] != "object_array_owner":
        raise WireError("Object-array base must own reference slots")
    return base["state"]


@dataclass(frozen=True)
class ObjectArrayCodec:
    kind: str
    immutable: bool = False

    def matches(self, value):
        import numpy as np

        return (
            type(value) is np.ndarray
            and value.dtype.kind == "O"
            and (value.base is None) == (self.kind == "object_array_owner")
        )

    def state(self, value, ref):
        import numpy as np

        if value.dtype != np.dtype(object) or value.dtype.metadata is not None:
            raise WireError("Object dtype metadata requires another graph codec")
        if value.flags.writebackifcopy:
            raise WireError("Object write-back storage requires another graph codec")
        state = {
            "itemsize": value.itemsize,
            "shape": list(value.shape),
            "strides": list(value.strides),
            "writeable": bool(value.flags.writeable),
            "aligned": bool(value.flags.aligned),
        }
        proxy, size = slot_geometry(state)
        if self.kind == "object_array_owner":
            if not value.flags.owndata or not (
                value.flags.c_contiguous or value.flags.f_contiguous
            ):
                raise WireError("Unsupported object-array owner storage")
            owner_order(proxy)
            slot_bounds(state, size, 0)
            # Iterate only validated owning slots, never a view's possibly forged addresses.
            state["items"] = [ref(item) for item in value.ravel(order="K")]
        else:
            base = value.base
            if (
                type(base) is not np.ndarray
                or base.dtype != np.dtype(object)
                or base.base is not None
                or not base.flags.owndata
            ):
                raise WireError("External or numeric object-array owner is unsupported")
            state["base"] = ref(base)
            state["offset"] = (
                value.__array_interface__["data"][0] - base.__array_interface__["data"][0]
            )
            slot_bounds(state, base.nbytes, state["offset"])
        return state

    def validate(self, state, index):
        fields(
            state, COMMON | ({"items"} if self.kind == "object_array_owner" else {"base", "offset"})
        )
        proxy, size = slot_geometry(state)
        if self.kind == "object_array_owner":
            owner_order(proxy)
            slot_bounds(state, size, 0)
            if type(state["items"]) is not list or len(state["items"]) != size // 8:
                raise WireError("Object-array reference count differs from storage")
        else:
            base = base_record(state, index)
            OBJECT_ARRAY_CODECS["object_array_owner"].validate(base, index)
            slot_bounds(state, slot_geometry(base)[1], state["offset"])

    def tokens(self, state):
        return state["items"] if self.kind == "object_array_owner" else (state["base"],)

    def array_bytes(self, state):
        return slot_geometry(state)[1] if self.kind == "object_array_owner" else 0

    def matrix_refs(self, state):
        return ()

    def validate_update(self, previous, state):
        if slot_geometry(previous)[1] != slot_geometry(state)[1]:
            raise WireError("Exported object-array storage resizing requires another codec")
        if self.kind == "object_array_view" and any(
            previous[k] != state[k] for k in ("base", "offset")
        ):
            raise WireError("Exported object-array base/offset changes require another codec")

    def allocate(self, state, index):
        import numpy as np

        if self.kind == "object_array_view":
            return None
        proxy, _ = slot_geometry(state)
        result = np.empty(tuple(state["shape"]), dtype=object, order=owner_order(proxy))
        result.strides = tuple(state["strides"])
        return result

    def populate(self, target, state, resolve):
        import numpy as np

        return np.ndarray(
            tuple(state["shape"]),
            dtype=object,
            buffer=resolve(state["base"]["ref"]),
            offset=state["offset"],
            strides=tuple(state["strides"]),
        )

    def prepare(self, state, resolve, index):
        from graybench.graph_types import token_value

        items = None
        if self.kind == "object_array_owner":
            items = tuple(token_value(token, resolve) for token in state["items"])
        return (
            items,
            ArrayUpdate(None, state["writeable"], state["aligned"]),
            (tuple(state["shape"]), tuple(state["strides"])),
        )

    def apply(self, target, prepared):
        import numpy as np

        items, flags, (shape, strides) = prepared
        apply_array_geometry(target, (np.dtype(object), shape, strides))
        if items is not None:
            target.flags.writeable = True
            flat = target.ravel(order="K")
            # Slice assignment can interpret nested objects as array dimensions.
            # Scalar slot assignment preserves each referenced object verbatim.
            for i, item in enumerate(items):
                flat[i] = item
            target.flags.writeable = flags.writeable
        ArrayCodec("ndarray_view").apply(target, flags)


OBJECT_ARRAY_CODECS = {
    kind: ObjectArrayCodec(kind) for kind in ("object_array_owner", "object_array_view")
}

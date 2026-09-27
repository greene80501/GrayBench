"""Registered SciPy capsule, root array and alias nodes for adapted runtimes."""

import base64
from dataclasses import dataclass

from graybench.circuit_wire import WireError, fields
from graybench.graph_numeric import (
    ArrayUpdate,
    apply_array_geometry,
    bounds,
    geometry,
    numeric_dtype,
)

ROOT_FIELDS = {"dtype", "dtype_char", "shape", "strides", "writeable", "aligned", "base"}
CAP_FIELDS = {"dtype_char", "origin_shape", "capacity", "bytes", "root"}
NATIVE_CODES = "fdFD"
MAX_NATIVE_BYTES = 16 * 1024 * 1024


def native_module():
    from scipy.linalg import _internal_matfuncs

    return _internal_matfuncs


def registered_native_root(value):
    import numpy as np

    if type(value) is not np.ndarray or type(value.base).__name__ != "PyCapsule":
        return False
    helper = getattr(native_module(), "_graybench_storage_descriptor", None)
    if helper is None:
        return False
    try:
        descriptor = helper(value.base)
    except (TypeError, ValueError):
        return False
    return descriptor[3] is value


def native_bytes(state):
    capacity = state["capacity"]
    encoded = state["bytes"]
    if type(encoded) is not str or len(encoded) != 4 * ((capacity + 2) // 3):
        raise WireError("Native storage byte length mismatch")
    try:
        data = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise WireError("Invalid native storage bytes") from exc
    if len(data) != capacity or base64.b64encode(data).decode("ascii") != encoded:
        raise WireError("Noncanonical native storage bytes")
    return data


def native_capacity(state):
    import numpy as np

    fields(state, CAP_FIELDS)
    code, shape, capacity = (
        state["dtype_char"],
        state["origin_shape"],
        state["capacity"],
    )
    if (
        type(code) is not str
        or code not in NATIVE_CODES
        or type(shape) is not list
        or len(shape) != 2
        or any(type(n) is not int or not 1 <= n <= MAX_NATIVE_BYTES for n in shape)
        or type(capacity) is not int
        or not 1 <= capacity <= MAX_NATIVE_BYTES
        or shape[0] * shape[1] * np.dtype(code).itemsize != capacity
    ):
        raise WireError("Invalid native allocation descriptor")
    native_bytes(state)
    return capacity


@dataclass(frozen=True)
class NativeCapsuleCodec:
    kind: str = "native_capsule"
    immutable: bool = False

    def matches(self, value):
        return type(value).__name__ == "PyCapsule"

    def state(self, value, ref):
        try:
            code, shape, capacity, root = native_module()._graybench_storage_descriptor(value)
            data = native_module()._graybench_storage_read(value)
        except (AttributeError, TypeError, ValueError) as exc:
            raise WireError("Unregistered native capsule") from exc
        if root is not None and root.base is not value:
            raise WireError("Registered native root lost its capsule base")
        return {
            "dtype_char": code,
            "origin_shape": list(shape),
            "capacity": capacity,
            "bytes": base64.b64encode(data).decode("ascii"),
            "root": None if root is None else ref(root),
        }

    def validate(self, state, index):
        native_capacity(state)
        token = state["root"]
        if token is None:
            return
        if type(token) is not dict or set(token) != {"ref"} or type(token["ref"]) is not str:
            raise WireError("Invalid native root reference")
        record = index.get(token["ref"])
        if record is None or record["kind"] != "native_root":
            raise WireError("Native capsule root must be a registered array")

    def validate_record(self, handle, state, index):
        self.validate(state, index)
        token = state["root"]
        if token is not None and index[token["ref"]]["state"].get("base") != {"ref": handle}:
            raise WireError("Native capsule/root relation is not reciprocal")

    def validate_update(self, previous, state):
        if any(previous[key] != state[key] for key in CAP_FIELDS - {"bytes"}):
            raise WireError("Native allocation identity or extent changed")

    def array_bytes(self, state):
        return state["capacity"]

    def matrix_refs(self, state):
        return ()

    def tokens(self, state):
        return () if state["root"] is None else (state["root"],)

    def allocate(self, state, index):
        if state["root"] is not None:
            return None
        root = native_module()._graybench_storage_new(
            state["dtype_char"], tuple(state["origin_shape"])
        )
        return root.base

    def populate(self, target, state, resolve):
        return resolve(state["root"]["ref"]).base if state["root"] is not None else target

    def prepare(self, state, resolve, index):
        return native_bytes(state)

    def apply(self, target, prepared):
        native_module()._graybench_storage_write(target, prepared)


@dataclass(frozen=True)
class NativeRootCodec:
    kind: str = "native_root"
    immutable: bool = False

    def matches(self, value):
        return registered_native_root(value)

    def state(self, value, ref):
        return {
            "dtype": value.dtype.str,
            "dtype_char": value.dtype.char,
            "shape": list(value.shape),
            "strides": list(value.strides),
            "writeable": bool(value.flags.writeable),
            "aligned": bool(value.flags.aligned),
            "base": ref(value.base),
        }

    def validate(self, state, index):
        fields(state, ROOT_FIELDS)
        geometry(state)
        token = state["base"]
        if type(token) is not dict or set(token) != {"ref"} or type(token["ref"]) is not str:
            raise WireError("Invalid registered root base")
        capsule = index.get(token["ref"])
        if capsule is None or capsule["kind"] != "native_capsule":
            raise WireError("Registered root requires native capsule base")
        bounds(state, native_capacity(capsule["state"]), 0)

    def validate_record(self, handle, state, index):
        self.validate(state, index)
        capsule = index[state["base"]["ref"]]
        if capsule["state"]["root"] != {"ref": handle}:
            raise WireError("Registered root/capsule relation is not reciprocal")

    def validate_update(self, previous, state):
        if previous["base"] != state["base"] or (not previous["writeable"] and state["writeable"]):
            raise WireError("Registered root base or readonly state changed")

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()

    def tokens(self, state):
        return (state["base"],)

    def owned_tokens(self, state):
        return (state["base"],)

    def owner_children(self, target, state):
        return {state["base"]["ref"]: target.base}

    def transition_owner(self, target, previous, state, index):
        if not registered_native_root(target):
            raise WireError("Registered native root lost its storage identity")

    def allocate(self, state, index):
        capsule = index[state["base"]["ref"]]["state"]
        return native_module()._graybench_storage_new(
            capsule["dtype_char"], tuple(capsule["origin_shape"])
        )

    def populate(self, target, state, resolve):
        return target

    def prepare(self, state, resolve, index):
        return ArrayUpdate(
            None,
            state["writeable"],
            state["aligned"],
            (numeric_dtype(state), tuple(state["shape"]), tuple(state["strides"])),
        )

    def apply(self, target, prepared):
        apply_array_geometry(target, prepared.geometry)
        if target.flags.writeable != prepared.writeable:
            target.flags.writeable = prepared.writeable
        target.flags.aligned = prepared.aligned


NATIVE_CODECS = {"native_capsule": NativeCapsuleCodec(), "native_root": NativeRootCodec()}

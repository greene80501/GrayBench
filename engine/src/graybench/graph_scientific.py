"""Fixed scientific component graphs; no constructors that copy or repair values."""

import json
import math
from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError, fields
from graybench.graph_numeric import geometry
from graybench.scientific_wire import MAX_BYTES


@cache
def classes():
    from qiskit.quantum_info import (
        Choi,
        Clifford,
        DensityMatrix,
        Operator,
        ScalarOp,
        StabilizerState,
        Statevector,
    )
    from qiskit.quantum_info.operators.op_shape import OpShape

    return dict(
        op_shape=OpShape,
        statevector=Statevector,
        density_matrix=DensityMatrix,
        operator=Operator,
        choi=Choi,
        scalar_op=ScalarOp,
        clifford=Clifford,
        stabilizer=StabilizerState,
    )


SHAPE_FIELDS = (
    ("num_l", "_num_qargs_l"),
    ("num_r", "_num_qargs_r"),
    ("dims_l", "_dims_l"),
    ("dims_r", "_dims_r"),
)
STATE_FIELDS = (("data", "_data"), ("shape", "_op_shape"), ("rng", "_rng_generator"))
OP_FIELDS = (("data", "_data"), ("shape", "_op_shape"), ("qargs", "_qargs"))
ATTRIBUTES = {
    "op_shape": SHAPE_FIELDS,
    "statevector": STATE_FIELDS,
    "density_matrix": STATE_FIELDS,
    "stabilizer": STATE_FIELDS,
    "operator": OP_FIELDS,
    "choi": OP_FIELDS,
    "clifford": (("data", "tableau"), ("shape", "_op_shape"), ("qargs", "_qargs")),
    "scalar_op": (("coefficient", "_coeff"), ("shape", "_op_shape"), ("qargs", "_qargs")),
}


def node(token, index, kinds):
    if type(token) is not dict or set(token) != {"ref"} or type(token["ref"]) is not str:
        raise WireError("Expected scientific component reference")
    result = index.get(token["ref"])
    if result is None or result["kind"] not in kinds:
        raise WireError("Invalid scientific component kind")
    return result


def tuple_items(token, index):
    state = node(token, index, {"tuple"})["state"]
    if type(state) is not list:
        raise WireError("Invalid scientific dimension tuple")
    return state


def shape_dims(state, index):
    fields(state, {key for key, _ in SHAPE_FIELDS} | {"attributes"})
    result = []
    for side in ("l", "r"):
        count = state["num_" + side]
        if type(count) is not int or not 0 <= count <= 256:
            raise WireError("Invalid scientific subsystem count")
        dims = state["dims_" + side]
        if dims is None:
            result.append((2,) * count)
            continue
        values = tuple_items(dims, index)
        if len(values) != count or any(
            type(n) is not int or not 1 <= n <= MAX_BYTES for n in values
        ):
            raise WireError("Invalid scientific subsystem dimensions")
        result.append(tuple(values))
    return tuple(result)


def array_state(token, index):
    record = node(token, index, {"ndarray_owner", "ndarray_view"})
    state = record["state"]
    expected = {"dtype", "dtype_char", "shape", "strides", "writeable", "aligned"}
    fields(
        state, expected | ({"bytes"} if record["kind"] == "ndarray_owner" else {"base", "offset"})
    )
    # Referenced nodes can follow the wrapper in the message. Validate their
    # structural fields here; the array codec separately validates storage bytes.
    dtype, _ = geometry(state)
    return tuple(state["shape"]), dtype


def clifford_width(state, index):
    fields(state, {key for key, _ in ATTRIBUTES["clifford"]} | {"attributes"})
    shape = node(state["shape"], index, {"op_shape"})["state"]
    left, right = shape_dims(shape, index)
    n = len(left)
    if (
        left != right
        or left != (2,) * n
        or shape["dims_l"] is not None
        or shape["dims_r"] is not None
    ):
        raise WireError("Clifford requires a qubit OpShape")
    actual, dtype = array_state(state["data"], index)
    if actual != (2 * n, 2 * n + 1) or dtype.kind != "b":
        raise WireError("Clifford tableau shape or dtype mismatch")
    return n


def validate_attributes(state, index, names):
    entries = node(state["attributes"], index, {"dict"})["state"]
    expected = {attribute: state[key] for key, attribute in names}
    if type(entries) is not list or len(entries) != len(expected):
        raise WireError("Scientific instance dictionary fields differ from schema")
    actual = {}
    for entry in entries:
        if (
            type(entry) is not list
            or len(entry) != 2
            or type(entry[0]) is not str
            or entry[0] not in expected
            or entry[0] in actual
        ):
            raise WireError("Invalid scientific instance dictionary field")
        actual[entry[0]] = entry[1]
    # Compare canonical tokens, not Python numeric equality (True != integer 1).
    try:
        actual_wire = json.dumps(actual, sort_keys=True, allow_nan=False)
        expected_wire = json.dumps(expected, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise WireError("Invalid scientific instance dictionary token") from exc
    if actual_wire != expected_wire:
        raise WireError("Scientific instance dictionary and component fields diverge")


@dataclass(frozen=True)
class ScientificCodec:
    kind: str
    immutable: bool = False

    def matches(self, value):
        return type(value) is classes()[self.kind]

    def state(self, value, ref):
        names = ATTRIBUTES[self.kind]
        if set(vars(value)) != {attribute for _, attribute in names}:
            raise WireError("Extra scientific instance state requires a graph codec")
        if (
            self.kind in {"statevector", "density_matrix", "stabilizer"}
            and value._rng_generator is not None
        ):
            raise WireError("Explicit scientific RNG requires a graph codec")
        return {
            **{key: ref(getattr(value, attribute)) for key, attribute in names},
            "attributes": ref(vars(value)),
        }

    def validate(self, state, shape_index):
        fields(state, {key for key, _ in ATTRIBUTES[self.kind]} | {"attributes"})
        validate_attributes(state, shape_index, ATTRIBUTES[self.kind])
        if self.kind == "op_shape":
            shape_dims(state, shape_index)
            return
        left, right = shape_dims(
            node(state["shape"], shape_index, {"op_shape"})["state"], shape_index
        )
        if "rng" in state and state["rng"] is not None:
            raise WireError("Explicit scientific RNG requires a graph codec")
        if "qargs" in state and state["qargs"] is not None:
            qargs = tuple_items(state["qargs"], shape_index)
            if len(qargs) not in (len(left), len(right)) or any(
                type(n) is not int or n < 0 for n in qargs
            ):
                raise WireError("Invalid scientific bound subsystem indices")
        dl, dr = math.prod(left), math.prod(right)
        if self.kind == "scalar_op":
            if dl != dr:
                raise WireError("ScalarOp dimensions are not square")
            coefficient = state["coefficient"]
            if type(coefficient) is dict and set(coefficient) == {"ref"}:
                node(coefficient, shape_index, {"numpy_scalar"})
            else:
                from graybench.graph_types import scalar_value

                if type(scalar_value(coefficient)) not in (bool, int, float, complex):
                    raise WireError("Invalid scalar operator coefficient")
            return
        if self.kind == "clifford":
            clifford_width(state, shape_index)
            return
        if self.kind == "stabilizer":
            component = node(state["data"], shape_index, {"clifford"})
            n = clifford_width(component["state"], shape_index)
            if left or right != (2,) * n:
                raise WireError("Stabilizer OpShape differs from its Clifford")
            return
        actual, _ = array_state(state["data"], shape_index)
        if self.kind == "statevector":
            expected = (dl,)
            if right:
                raise WireError("Statevector has unexpected input subsystems")
        elif self.kind == "density_matrix":
            expected = (dl, dl)
            if left != right:
                raise WireError("DensityMatrix subsystem dimensions differ")
        elif self.kind == "operator":
            expected = (dl, dr)
        else:
            expected = (dl * dr,) * 2
        if actual != expected:
            raise WireError("Scientific array shape differs from subsystem dimensions")

    def tokens(self, state):
        yield from (state[key] for key, _ in ATTRIBUTES[self.kind])
        yield state["attributes"]

    def allocate(self, state, shape_index):
        return object.__new__(classes()[self.kind])

    def prepare(self, state, resolve, shape_index):
        return resolve(state["attributes"]["ref"])

    def apply(self, target, prepared):
        # The dictionary node is reconciled by the container codec. Its exact
        # fixed fields were validated above; no candidate-defined attributes or
        # constructors are invoked. Assigning it preserves explicit vars aliases.
        object.__setattr__(target, "__dict__", prepared)

    def array_bytes(self, state):
        return 0  # Referenced storage is charged by its own numeric node.

    def matrix_refs(self, state):
        return (
            (state["data"],)
            if self.kind in {"operator", "choi", "density_matrix", "clifford"}
            else ()
        )

    def validate_update(self, previous, state):
        pass  # Component replacements and consistent dimension changes are allowed.


SCIENTIFIC_CODECS = {name: ScientificCodec(name) for name in ATTRIBUTES}

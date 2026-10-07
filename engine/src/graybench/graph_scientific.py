"""Fixed scientific component graphs; no constructors that copy or repair values."""

import json
import math
from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError, fields
from graybench.graph_numeric import geometry, numeric_dtype
from graybench.scientific_wire import MAX_BYTES, dihedral_shapes


@cache
def classes():
    from qiskit.quantum_info import (
        Choi,
        Clifford,
        CNOTDihedral,
        DensityMatrix,
        Operator,
        PauliList,
        ScalarOp,
        SparsePauliOp,
        StabilizerState,
        Statevector,
    )
    from qiskit.quantum_info.operators.dihedral.polynomial import SpecialPolynomial
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
        cnot_dihedral=CNOTDihedral,
        special_polynomial=SpecialPolynomial,
        pauli_list=PauliList,
        sparse_pauli_op=SparsePauliOp,
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
    "cnot_dihedral": (
        ("qubits", "_num_qubits"),
        ("poly", "poly"),
        ("linear", "linear"),
        ("shift", "shift"),
        ("shape", "_op_shape"),
        ("qargs", "_qargs"),
    ),
    "special_polynomial": tuple(
        (name, name)
        for name in ("n_vars", "nc2", "nc3", "weight_0", "weight_1", "weight_2", "weight_3")
    ),
    "pauli_list": (
        ("z", "_z"),
        ("x", "_x"),
        ("phase", "_phase"),
        ("count", "_num_paulis"),
        ("shape", "_op_shape"),
        ("qargs", "_qargs"),
    ),
    "sparse_pauli_op": (
        ("coeffs", "_coeffs"),
        ("paulis", "_pauli_list"),
        ("shape", "_op_shape"),
        ("qargs", "_qargs"),
    ),
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


def integer_token(token, index):
    if type(token) is int:
        return
    scalar = node(token, index, {"numpy_scalar"})["state"]
    fields(scalar, {"kind", "dtype", "dtype_char", "shape", "bytes"})
    if numeric_dtype(scalar).kind not in "iu":
        raise WireError("Expected integer polynomial component")


def qubit_width(shape, index):
    left, right = shape_dims(shape, index)
    n = len(left)
    if (
        left != right
        or left != (2,) * n
        or shape["dims_l"] is not None
        or shape["dims_r"] is not None
    ):
        raise WireError("Expected matching implicit qubit dimensions")
    return n


def polynomial_width(state, index):
    fields(state, {key for key, _ in ATTRIBUTES["special_polynomial"]} | {"attributes"})
    n = state["n_vars"]
    shapes = dihedral_shapes(n)
    if (
        type(state["nc2"]) is not int
        or type(state["nc3"]) is not int
        or (state["nc2"], state["nc3"]) != (math.comb(n, 2), math.comb(n, 3))
    ):
        raise WireError("Polynomial combination counts differ from variable count")
    integer_token(state["weight_0"], index)
    for key in ("weight_1", "weight_2", "weight_3"):
        if array_state(state[key], index)[0] != shapes[key]:
            raise WireError("Polynomial coefficient array shape mismatch")
    return n


def pauli_shape(state, index):
    fields(state, {key for key, _ in ATTRIBUTES["pauli_list"]} | {"attributes"})
    shape = node(state["shape"], index, {"op_shape"})["state"]
    n = qubit_width(shape, index)
    count = state["count"]
    if type(count) is not int or not 0 <= count <= MAX_BYTES:
        raise WireError("Invalid Pauli row count")
    for key in ("z", "x"):
        actual, dtype = array_state(state[key], index)
        if actual != (count, n) or dtype.kind != "b":
            raise WireError("Pauli symplectic array shape or dtype mismatch")
    actual, dtype = array_state(state["phase"], index)
    if actual != (count,) or dtype.kind not in "iu":
        raise WireError("Pauli phase array shape or dtype mismatch")
    return count, n


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
        if self.kind == "special_polynomial":
            polynomial_width(state, shape_index)
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
        if self.kind == "cnot_dihedral":
            n = state["qubits"]
            shapes = dihedral_shapes(n)
            shape = node(state["shape"], shape_index, {"op_shape"})["state"]
            poly = node(state["poly"], shape_index, {"special_polynomial"})["state"]
            if qubit_width(shape, shape_index) != n or polynomial_width(poly, shape_index) != n:
                raise WireError("CNOTDihedral width differs from its components")
            if array_state(state["linear"], shape_index)[0] != shapes["linear"]:
                raise WireError("CNOTDihedral linear shape mismatch")
            shift = node(state["shift"], shape_index, {"list", "ndarray_owner", "ndarray_view"})
            if shift["kind"] == "list":
                if type(shift["state"]) is not list or len(shift["state"]) != n:
                    raise WireError("CNOTDihedral shift list length mismatch")
                for token in shift["state"]:
                    integer_token(token, shape_index)
            elif array_state(state["shift"], shape_index)[0] != shapes["shift"]:
                raise WireError("CNOTDihedral shift array shape mismatch")
            return
        if self.kind == "pauli_list":
            pauli_shape(state, shape_index)
            return
        if self.kind == "sparse_pauli_op":
            paulis = node(state["paulis"], shape_index, {"pauli_list"})["state"]
            rows, width = pauli_shape(paulis, shape_index)
            shape = node(state["shape"], shape_index, {"op_shape"})["state"]
            if qubit_width(shape, shape_index) != width:
                raise WireError("SparsePauliOp width differs from PauliList")
            coeff_record = node(
                state["coeffs"],
                shape_index,
                {"ndarray_owner", "ndarray_view", "object_array_owner", "object_array_view"},
            )
            if coeff_record["kind"].startswith("object_array_"):
                from graybench.graph_object_arrays import OBJECT_ARRAY_CODECS

                OBJECT_ARRAY_CODECS[coeff_record["kind"]].validate(
                    coeff_record["state"], shape_index
                )
                coeff_shape = tuple(coeff_record["state"]["shape"])
            else:
                coeff_shape = array_state(state["coeffs"], shape_index)[0]
            if coeff_shape != (rows,):
                raise WireError("Sparse coefficient count differs from Pauli rows")
            return
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
        if self.kind == "cnot_dihedral":
            return (state["linear"],)
        if self.kind == "pauli_list":
            return (state["z"], state["x"])
        return (
            (state["data"],)
            if self.kind in {"operator", "choi", "density_matrix", "clifford"}
            else ()
        )

    def validate_update(self, previous, state):
        pass  # Component replacements and consistent dimension changes are allowed.


SCIENTIFIC_CODECS = {name: ScientificCodec(name) for name in ATTRIBUTES}

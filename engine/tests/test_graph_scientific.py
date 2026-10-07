import copy

import numpy as np
import pytest
from qiskit import QuantumCircuit
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

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas(**limits):
    return tuple(
        GraphArena(side=side, session="science", limits=GraphLimits(**limits))
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    return receiver.commit(
        receiver.prepare(sender.snapshot({"value": value}, sequence=sequence), sequence=sequence)
    )["value"]


@pytest.mark.parametrize(
    "cls,shape", [(Statevector, (4,)), (DensityMatrix, (4, 4)), (Operator, (4, 4)), (Choi, (4, 4))]
)
def test_wrappers_share_numeric_data_and_return_original_instances(cls, shape):
    judge, candidate = arenas()
    data = np.arange(np.prod(shape), dtype=np.complex128).reshape(shape).copy()
    left, right = cls(data), cls(data)
    assert left.data is right.data is data
    a, b, array = transfer(judge, candidate, (left, right, data))
    assert a is not b and a.data is b.data is array
    a.data.flat[0] = 17 - 3j
    result = transfer(candidate, judge, b)
    assert result is right and left.data is right.data is data
    assert data.flat[0] == 17 - 3j


def test_equal_data_replacement_is_distinct_while_detached_array_remains_live():
    judge, candidate = arenas()
    original = Statevector([1, 0])
    held = original.data
    remote = transfer(judge, candidate, original)
    old = remote.data
    remote._data = old.copy()
    transfer(candidate, judge, remote)
    assert original.data is not held
    np.testing.assert_array_equal(original.data, [1, 0])
    transfer(judge, candidate, None, 2)
    old[1] = 7
    transfer(candidate, judge, None, 2)
    assert held[1] == 7 and original.data[1] == 0


def test_opshape_and_dimension_tuple_aliases_survive_valid_shape_updates():
    judge, candidate = arenas()
    dims = (2, 3)
    a = Operator(np.eye(6), input_dims=dims, output_dims=dims)
    b = Operator(a)
    b._op_shape = a._op_shape
    shape = a._op_shape
    assert shape._dims_l is dims and shape._dims_r is dims
    left, right, remote_shape, remote_dims = transfer(judge, candidate, (a, b, shape, dims))
    assert left._op_shape is right._op_shape is remote_shape
    assert remote_shape._dims_l is remote_shape._dims_r is remote_dims
    remote_shape._dims_l = (3, 2)
    result = transfer(candidate, judge, left)
    assert result is a and a._op_shape is b._op_shape is shape
    assert a.output_dims() == b.output_dims() == (3, 2)
    assert a.input_dims() == (2, 3)


def test_bound_qargs_tuple_is_shared_with_explicit_argument():
    judge, candidate = arenas()
    qargs = (7, 2)
    operator = Operator(np.eye(4))(qargs)
    assert operator.qargs is qargs
    result, indices = transfer(judge, candidate, (operator, qargs))
    assert result.qargs is indices and indices == (7, 2)


def test_invalid_physical_values_are_preserved_without_constructor_repair():
    judge, candidate = arenas()
    state = Statevector([2, 0])
    density = DensityMatrix([[1, 0], [0, -1]])
    operator = Operator([[2, 0], [0, 2]])
    a, b, c = transfer(judge, candidate, (state, density, operator))
    assert not a.is_valid() and not b.is_valid() and not c.is_unitary()
    np.testing.assert_array_equal(a.data, [2, 0])
    np.testing.assert_array_equal(b.data, [[1, 0], [0, -1]])
    np.testing.assert_array_equal(c.data, [[2, 0], [0, 2]])


def test_scalar_operator_preserves_coefficient_type_shape_and_updates():
    judge, candidate = arenas()
    value = ScalarOp((2, 3), coeff=np.complex64(3 + 2j))
    coefficient = value.coeff
    remote, coeff = transfer(judge, candidate, (value, coefficient))
    assert type(remote.coeff) is np.complex64 and remote.coeff is coeff
    assert remote.input_dims() == remote.output_dims() == (2, 3)
    remote._coeff = -2j
    assert transfer(candidate, judge, remote) is value
    assert value.coeff == -2j


@pytest.mark.parametrize("qubits", [0, 1, 3, 20])
def test_clifford_and_stabilizer_preserve_nested_tableau_aliases(qubits):
    judge, candidate = arenas()
    clifford = Clifford(QuantumCircuit(qubits))
    state = StabilizerState(clifford)
    table = state.clifford.tableau
    result, component, tableau = transfer(judge, candidate, (state, state.clifford, table))
    assert result.clifford is component and component.tableau is tableau
    assert result.num_qubits == qubits
    if qubits:
        tableau[0, -1] = True
    assert transfer(candidate, judge, result) is state
    assert state.clifford.tableau is table
    if qubits:
        assert table[0, -1]


def test_invalid_symplectic_tableau_is_not_normalized():
    judge, candidate = arenas()
    tableau = np.zeros((2, 3), dtype=bool)
    value = Clifford(tableau, validate=False)
    result = transfer(judge, candidate, value)
    assert not result.is_unitary()
    np.testing.assert_array_equal(result.tableau, np.zeros((2, 3), dtype=bool))


@pytest.mark.parametrize("change", ["dims", "count", "data", "shape_class", "rng", "extra"])
def test_malformed_late_scientific_updates_do_not_mutate_existing_values(change):
    judge, candidate = arenas()
    original = Statevector([1, 0])
    remote = transfer(judge, candidate, original)
    remote.data[0] = 9
    wire = candidate.snapshot({"value": remote}, sequence=1)
    bad = copy.deepcopy(wire)
    wrapper = next(n for n in bad["nodes"] if n["kind"] == "statevector")
    shape = next(n for n in bad["nodes"] if n["kind"] == "op_shape")
    if change == "dims":
        shape["state"]["dims_l"] = {"ref": wrapper["id"]}
    elif change == "count":
        shape["state"]["num_l"] = 2
    elif change == "data":
        wrapper["state"]["data"] = {"ref": shape["id"]}
    elif change == "shape_class":
        wrapper["state"]["shape"] = {"ref": wrapper["id"]}
    elif change == "rng":
        wrapper["state"]["rng"] = 42
    else:
        wrapper["state"]["unexpected"] = 1
    # Keep the mirrored instance dictionary consistent so these cases exercise
    # semantic component validation, not just disagreement between two fields.
    records = {n["id"]: n for n in bad["nodes"]}
    for record, names in (
        (wrapper, {"data": "_data", "shape": "_op_shape", "rng": "_rng_generator"}),
        (
            shape,
            {
                "num_l": "_num_qargs_l",
                "num_r": "_num_qargs_r",
                "dims_l": "_dims_l",
                "dims_r": "_dims_r",
            },
        ),
    ):
        entries = records[record["state"]["attributes"]["ref"]]["state"]
        for key, attribute in names.items():
            next(pair for pair in entries if pair[0] == attribute)[1] = record["state"][key]
    with pytest.raises(WireError):
        judge.prepare(bad, sequence=1)
    np.testing.assert_array_equal(original.data, [1, 0])


def test_matrix_limit_counts_shared_storage_once_and_receiver_enforces_its_limit():
    judge, candidate = arenas(matrix_bytes=64)
    data = np.eye(2, dtype=np.complex128)
    values = (Operator(data), DensityMatrix(data))
    a, b = transfer(judge, candidate, values)
    assert a.data is b.data
    judge, _ = arenas(matrix_bytes=64)
    with pytest.raises(WireError):
        judge.snapshot({"value": (Operator(data), Operator(data.copy()))}, sequence=1)
    judge, _ = arenas()
    _, candidate = arenas(matrix_bytes=63)
    with pytest.raises(WireError):
        candidate.prepare(judge.snapshot({"value": values}, sequence=1), sequence=1)


def test_extra_instance_state_and_seeded_rng_are_not_silently_discarded():
    judge, _ = arenas()
    state = Statevector([1, 0])
    state.seed(13)
    with pytest.raises(WireError):
        judge.snapshot({"value": state}, sequence=1)
    operator = Operator(np.eye(2))
    operator.user_data = {"held": []}
    with pytest.raises(WireError):
        judge.snapshot({"value": operator}, sequence=1)


def test_standalone_opshape_preserves_none_versus_explicit_qubit_dimensions():
    judge, candidate = arenas()
    implicit = OpShape(num_qargs_l=1)
    explicit = OpShape(dims_l=(2,))
    a, b = transfer(judge, candidate, (implicit, explicit))
    assert a.dims_l() == b.dims_l() == (2,)
    assert a.num_qubits == 1 and b.num_qubits is None


def test_explicit_instance_dictionaries_keep_identity_and_in_place_updates():
    judge, candidate = arenas()
    state = Statevector([1, 0])
    attributes = vars(state)
    shape_attributes = vars(state._op_shape)
    remote, mapping, shape_mapping = transfer(
        judge, candidate, (state, attributes, shape_attributes)
    )
    assert vars(remote) is mapping
    assert vars(remote._op_shape) is shape_mapping
    mapping["_data"] = np.array([0, 1], dtype=complex)
    transfer(candidate, judge, remote)
    assert vars(state) is attributes and vars(state._op_shape) is shape_attributes
    assert state.data is attributes["_data"]
    np.testing.assert_array_equal(state.data, [0, 1])


def test_two_wrappers_can_share_one_exact_instance_dictionary():
    judge, candidate = arenas()
    a, b = Operator(np.eye(2)), Operator(np.eye(2))
    b.__dict__ = a.__dict__
    left, right = transfer(judge, candidate, (a, b))
    assert left is not right and vars(left) is vars(right)
    right._data = np.zeros((2, 2), dtype=complex)
    assert left.data is right.data
    transfer(candidate, judge, (left, right))
    assert a.data is b.data and vars(a) is vars(b)
    assert not np.any(a.data)


@pytest.mark.parametrize("case", ["extra", "divergent", "boolean_count"])
def test_instance_dictionary_validation_rejects_forged_fields_before_mutation(case):
    judge, candidate = arenas()
    value = Statevector([1, 0])
    remote = transfer(judge, candidate, value)
    remote.data[0] = 4
    wire = candidate.snapshot({"value": remote}, sequence=1)
    records = {n["id"]: n for n in wire["nodes"]}
    shape = next(n for n in wire["nodes"] if n["kind"] == "op_shape")
    attrs = records[shape["state"]["attributes"]["ref"]]["state"]
    if case == "extra":
        attrs.append(["__class__", "os.system"])
    elif case == "divergent":
        next(pair for pair in attrs if pair[0] == "_num_qargs_l")[1] = 0
    else:
        next(pair for pair in attrs if pair[0] == "_num_qargs_l")[1] = True
    with pytest.raises(WireError):
        judge.prepare(wire, sequence=1)
    assert value.data[0] == 1 and value.num_qubits == 1


def test_data_and_opshape_can_change_consistently_without_replacing_wrapper():
    judge, candidate = arenas()
    state = Statevector([1, 0])
    held_shape = state._op_shape
    held_data = state.data
    remote = transfer(judge, candidate, state)
    remote._data = np.array([0, 0, 0, 1], dtype=complex)
    remote._op_shape._num_qargs_l = 2
    assert transfer(candidate, judge, remote) is state
    assert state._op_shape is held_shape and state.data is not held_data
    assert state.dims() == (2, 2)
    np.testing.assert_array_equal(state.data, [0, 0, 0, 1])
    np.testing.assert_array_equal(held_data, [1, 0])


def test_oversized_scalar_integer_is_a_wire_error_and_does_not_poison_sender():
    judge, candidate = arenas()
    value = ScalarOp(2, coeff=10**5000)
    with pytest.raises(WireError):
        judge.snapshot({"value": value}, sequence=1)
    value._coeff = 3
    result = transfer(judge, candidate, value)
    assert result.coeff == 3

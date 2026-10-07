import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.primitives import DataBin
from qiskit.quantum_info import CNOTDihedral, PauliList, SparsePauliOp

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas(**limits):
    return tuple(
        GraphArena(side=side, session="sparse", limits=GraphLimits(**limits))
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    return receiver.commit(
        receiver.prepare(sender.snapshot({"value": value}, sequence=sequence), sequence=sequence)
    )["value"]


def patch_state(wire, record, key, attribute, value):
    records = {r["id"]: r for r in wire["nodes"]}
    record["state"][key] = value
    attrs = records[record["state"]["attributes"]["ref"]]["state"]
    next(pair for pair in attrs if pair[0] == attribute)[1] = value


def test_dihedral_polynomial_arrays_and_dictionaries_preserve_aliases():
    judge, candidate = arenas()
    circuit = QuantumCircuit(3)
    circuit.t(1)
    circuit.cx(0, 2)
    value = CNOTDihedral(circuit)
    expected = value.to_matrix()
    remote, poly, weights, attributes = transfer(
        judge, candidate, (value, value.poly, value.poly.weight_1, vars(value.poly))
    )
    assert remote.poly is poly and poly.weight_1 is weights and vars(poly) is attributes
    np.testing.assert_allclose(remote.to_matrix(), expected, rtol=0, atol=1e-12)
    weights[1] = -7
    poly.weight_0 = np.int16(-19)
    assert transfer(candidate, judge, remote) is value
    assert value.poly.weight_1[1] == -7
    assert type(value.poly.weight_0) is np.int16 and value.poly.weight_0 == -19


@pytest.mark.parametrize("qubits", [1, 2, 3, 6])
def test_dihedral_shared_polynomial_and_integer_list_shift(qubits):
    judge, candidate = arenas()
    a = CNOTDihedral(QuantumCircuit(qubits))
    b = CNOTDihedral(QuantumCircuit(qubits))
    b.poly = a.poly
    shift = [np.int8(0) for _ in range(qubits)]
    a.shift = shift
    left, right, held = transfer(judge, candidate, (a, b, shift))
    assert left.poly is right.poly and left.shift is held
    assert type(left.shift) is list and type(left.shift[0]) is np.int8
    left.poly.weight_0 = 21
    held[0] = np.int8(1)
    transfer(candidate, judge, (left, right))
    assert a.poly is b.poly and a.poly.weight_0 == 21 and a.shift is shift and shift[0] == 1


def test_dihedral_wrong_numeric_values_are_not_repaired():
    judge, candidate = arenas()
    value = CNOTDihedral(QuantumCircuit(2))
    value.linear[:] = 3
    value.poly.weight_2[:] = 19
    value.shift[:] = -4
    remote = transfer(judge, candidate, value)
    np.testing.assert_array_equal(remote.linear, [[3, 3], [3, 3]])
    np.testing.assert_array_equal(remote.poly.weight_2, [19])
    np.testing.assert_array_equal(remote.shift, [-4, -4])


@pytest.mark.parametrize(
    "case", ["qubits", "polynomial_count", "polynomial_type", "linear", "constant"]
)
def test_invalid_dihedral_component_updates_are_atomic(case):
    judge, candidate = arenas()
    value = CNOTDihedral(QuantumCircuit(3))
    remote = transfer(judge, candidate, value)
    remote.poly.weight_1[0] = 5
    wire = candidate.snapshot({"value": remote}, sequence=1)
    record = next(r for r in wire["nodes"] if r["kind"] == "cnot_dihedral")
    poly = next(r for r in wire["nodes"] if r["kind"] == "special_polynomial")
    if case == "qubits":
        patch_state(wire, record, "qubits", "_num_qubits", 2)
    elif case == "polynomial_count":
        patch_state(wire, poly, "nc2", "nc2", 4)
    elif case == "polynomial_type":
        patch_state(wire, record, "poly", "poly", record["state"]["linear"])
    elif case == "linear":
        patch_state(wire, record, "linear", "linear", record["state"]["shift"])
    else:
        patch_state(wire, poly, "weight_0", "weight_0", True)
    with pytest.raises(WireError):
        judge.prepare(wire, sequence=1)
    assert value.poly.weight_1[0] == 0


def test_sparse_terms_coefficients_and_pauli_storage_stay_shared_without_simplifying():
    judge, candidate = arenas()
    value = SparsePauliOp(["X", "X", "-Y"], [1, 2, 3])
    remote, paulis, z, x, phase, coeff = transfer(
        judge,
        candidate,
        (value, value.paulis, value.paulis._z, value.paulis._x, value.paulis._phase, value.coeffs),
    )
    assert remote.paulis is paulis and paulis._z is z and paulis._x is x and paulis._phase is phase
    assert remote.coeffs is coeff
    assert remote.to_list() == [("X", 1 + 0j), ("X", 2 + 0j), ("Y", -3 + 0j)]
    coeff[1] = 5
    assert transfer(candidate, judge, remote) is value
    assert value.to_list() == [("X", 1 + 0j), ("X", 5 + 0j), ("Y", -3 + 0j)]


def test_sparse_wrappers_share_paulis_coefficients_and_bound_qargs():
    judge, candidate = arenas()
    a = SparsePauliOp(["XX", "ZY"], [1, 2])((2, 5))
    b = SparsePauliOp(["XX", "ZY"], [1, 2])
    b._pauli_list = a.paulis
    b._coeffs = a.coeffs
    left, right, qargs = transfer(judge, candidate, (a, b, a.qargs))
    assert left.paulis is right.paulis and left.coeffs is right.coeffs
    assert left.qargs is qargs and qargs == (2, 5)


def test_pauli_internal_phase_is_not_canonicalized_through_public_property():
    judge, candidate = arenas()
    value = PauliList(["Y", "X"])
    value._phase[:] = [13, -4]
    remote, phase = transfer(judge, candidate, (value, value._phase))
    assert remote._phase is phase
    np.testing.assert_array_equal(phase, [13, -4])
    np.testing.assert_array_equal(remote.phase, [0, 0])
    assert remote.to_labels() == ["Y", "X"]


def test_equal_pauli_replacement_and_later_detached_update():
    judge, candidate = arenas()
    value = SparsePauliOp(["X"], [1])
    held = value.paulis
    remote = transfer(judge, candidate, value)
    old = remote.paulis
    remote._pauli_list = old.copy()
    transfer(candidate, judge, remote)
    assert value.paulis is not held
    transfer(judge, candidate, None, 2)
    old._z[0, 0] = True
    transfer(candidate, judge, None, 2)
    assert held._z[0, 0] and not value.paulis._z[0, 0]


@pytest.mark.parametrize("case", ["count", "phase", "paulis", "coeffs"])
def test_bad_sparse_component_updates_do_not_mutate_existing_coefficients(case):
    judge, candidate = arenas()
    value = SparsePauliOp(["X", "Y"], [1, 2])
    remote, wrong = transfer(judge, candidate, (value, np.zeros(3, dtype=complex)))
    remote.coeffs[0] = 8
    wire = candidate.snapshot({"value": remote, "wrong": wrong}, sequence=1)
    record = next(r for r in wire["nodes"] if r["kind"] == "sparse_pauli_op")
    paulis = next(r for r in wire["nodes"] if r["kind"] == "pauli_list")
    if case == "count":
        patch_state(wire, paulis, "count", "_num_paulis", 3)
    elif case == "phase":
        patch_state(wire, paulis, "phase", "_phase", paulis["state"]["z"])
    elif case == "paulis":
        patch_state(wire, record, "paulis", "_pauli_list", record["state"]["coeffs"])
    else:
        patch_state(wire, record, "coeffs", "_coeffs", wire["roots"]["wrong"])
    with pytest.raises(WireError):
        judge.prepare(wire, sequence=1)
    np.testing.assert_array_equal(value.coeffs, [1, 2])


def test_pauli_shape_is_checked_when_nested_in_databin():
    judge, candidate = arenas()
    value = DataBin(shape=(2,), paulis=PauliList(["X", "Y"]))
    remote = transfer(judge, candidate, value)
    assert remote.paulis.shape == (2, 1)
    remote._data["paulis"] = PauliList(["X"])
    with pytest.raises(WireError, match="leading shape"):
        candidate.snapshot({"value": remote}, sequence=1)


def test_empty_pauli_rows_are_preserved():
    judge, candidate = arenas()
    value = PauliList(["XYZ"])[[]]
    result = transfer(judge, candidate, value)
    assert result.shape == (0, 3) and result._phase.shape == (0,)

"""Trusted standalone graph fixture; does not run candidates or score tasks."""

import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import qiskit
from qiskit import QuantumCircuit
from qiskit.primitives import DataBin, PrimitiveResult, PubResult
from qiskit.quantum_info import (
    Clifford,
    CNOTDihedral,
    DensityMatrix,
    ScalarOp,
    SparsePauliOp,
    Statevector,
)

import graybench.graph_wire as graph_module
from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def main():
    judge, candidate = (
        GraphArena(side=side, session="numeric-runtime-probe", limits=GraphLimits())
        for side in ("judge", "candidate")
    )

    def transfer(sender, receiver, values, sequence):
        wire = sender.snapshot({"value": values}, sequence=sequence)
        return receiver.commit(receiver.prepare(wire, sequence=sequence))["value"]

    checks = []
    array = np.arange(12, dtype=">i4")
    left, right = array[1:8], array[3:10]
    a, x, y = transfer(judge, candidate, (array, left, right), 1)
    assert x.base is y.base is a and np.shares_memory(x, y)
    x[2] = 91
    assert y[0] == 91
    returned = transfer(candidate, judge, y, 1)
    assert returned is right and left[2] == array[3] == 91
    checks.append("overlap_owner_and_in_place_return")

    a.flags.writeable = False
    assert x.flags.writeable
    x[0] = 17
    transfer(candidate, judge, a, 2)
    assert not array.flags.writeable and left.flags.writeable and array[1] == 17
    checks.append("writable_view_of_readonly_owner")

    for index, scalar_type in enumerate((np.intc, np.uintc, np.int64, np.float32), 3):
        scalar = scalar_type(3)
        source = np.array([1, 2, 3], dtype=scalar_type)
        result, value = transfer(judge, candidate, (source, scalar), index)
        assert result.dtype.type is source.dtype.type and type(value) is type(scalar)
        checks.append("numeric_type_" + scalar_type.__name__)

    backing = np.arange(24, dtype=np.uint8)
    view = np.ndarray((2,), dtype=np.int32, buffer=backing, offset=1)
    _, actual = transfer(judge, candidate, (backing, view), 7)
    assert not actual.flags.aligned
    checks.append("misaligned_storage")

    wire = candidate.snapshot({"value": actual}, sequence=7)
    record = next(n for n in wire["nodes"] if n["id"] == wire["roots"]["value"]["ref"])
    record["state"]["offset"] = 1000
    try:
        judge.prepare(wire, sequence=7)
    except WireError:
        pass
    else:
        raise AssertionError("Out-of-bounds storage was accepted")
    assert backing.tolist() == list(range(24))
    checks.append("malformed_storage_rejected")

    state = Statevector([1, 0])
    remote, attributes, data = transfer(judge, candidate, (state, vars(state), state.data), 8)
    assert vars(remote) is attributes and remote.data is data
    data[1] = 4
    assert transfer(candidate, judge, remote, 8) is state and state.data[1] == 4
    checks.append("scientific_instance_dictionary_and_data")

    density = transfer(judge, candidate, DensityMatrix([[1, 0], [0, -1]]), 9)
    assert not density.is_valid() and density.data[1, 1] == -1
    checks.append("invalid_physical_value_not_repaired")

    pub = PubResult(DataBin(a=np.array([1, 2])))
    result = PrimitiveResult([pub, pub])
    result.metadata["self"] = result
    remote, pubs, metadata = transfer(
        judge, candidate, (result, result._pub_results, result.metadata), 10
    )
    assert remote._pub_results is pubs and remote[0] is remote[1]
    assert remote.metadata is metadata and metadata["self"] is remote
    pubs.pop()
    assert transfer(candidate, judge, remote, 10) is result and len(result) == 1
    checks.append("primitive_result_lists_metadata_and_cycles")

    clifford = Clifford(QuantumCircuit(20))
    remote, table = transfer(judge, candidate, (clifford, clifford.tableau), 11)
    assert remote.tableau is table and remote.num_qubits == 20
    table[0, -1] = True
    assert transfer(candidate, judge, remote, 11) is clifford and clifford.tableau[0, -1]
    checks.append("clifford_tableau_identity")

    scalar = ScalarOp(2, coeff=10**5000)
    try:
        judge.snapshot({"value": scalar}, sequence=12)
    except WireError:
        pass
    else:
        raise AssertionError("Oversized integer escaped graph limits")
    scalar._coeff = 2
    assert transfer(judge, candidate, scalar, 12).coeff == 2
    checks.append("oversized_integer_recovery")

    dihedral = CNOTDihedral(QuantumCircuit(3))
    remote, poly, weights = transfer(
        judge, candidate, (dihedral, dihedral.poly, dihedral.poly.weight_1), 13
    )
    assert remote.poly is poly and poly.weight_1 is weights
    weights[0] = -7
    assert transfer(candidate, judge, remote, 13) is dihedral and dihedral.poly.weight_1[0] == -7
    checks.append("dihedral_polynomial_component_identity")

    sparse = SparsePauliOp(["X", "X", "-Y"], [1, 2, 3])
    remote, paulis, coeffs = transfer(judge, candidate, (sparse, sparse.paulis, sparse.coeffs), 14)
    assert remote.paulis is paulis and remote.coeffs is coeffs
    assert remote.to_list() == [("X", 1 + 0j), ("X", 2 + 0j), ("Y", -3 + 0j)]
    coeffs[1] = 5
    assert transfer(candidate, judge, remote, 14) is sparse and sparse.coeffs[1] == 5
    checks.append("sparse_pauli_storage_without_simplification")

    from qiskit.circuit import ParameterVector

    vector = ParameterVector("v", 3)
    remote, items, held, uid = transfer(
        judge, candidate, (vector, vector.params, vector[2], vector._root_uuid), 15
    )
    assert remote.params is items and remote[2] is held and remote._root_uuid is uid
    remote.resize(1)
    assert transfer(candidate, judge, remote, 15) is vector and len(vector) == 1
    remote.resize(3)
    assert remote[2] == held and remote[2] is not held and held.vector is remote
    transfer(candidate, judge, remote, 16)
    assert vector[2].vector is vector and len(vector.params) == 3
    checks.append("parameter_vector_resize_and_detached_identity")

    root = Path(graph_module.__file__).parent
    names = (
        "graph_wire.py",
        "graph_types.py",
        "graph_numeric.py",
        "circuit_wire.py",
        "scientific_wire.py",
        "graph_scientific.py",
        "graph_primitive.py",
        "graph_symbolic.py",
        "primitive_wire.py",
    )
    print(
        json.dumps(
            {
                "scope": "standalone_graph_development_probe",
                "production_bridge_integrated": False,
                "python": platform.python_version(),
                "system": platform.system(),
                "numpy": np.__version__,
                "qiskit": qiskit.__version__,
                "checks_passed": checks,
                "source_sha256": {
                    name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names
                },
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

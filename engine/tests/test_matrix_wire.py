import copy

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import UnitaryGate
from qiskit.quantum_info import Operator, random_unitary

from graybench.circuit_wire import WireError, decode_circuit, encode_circuit


def test_matrix_gate_preserves_operator_order_and_labels():
    circuit = QuantumCircuit(3)
    circuit.h(0)
    circuit.append(UnitaryGate(random_unitary(4, seed=19), label="matrix"), [2, 0])
    circuit.x(1)
    restored = decode_circuit(encode_circuit(circuit))
    np.testing.assert_allclose(Operator(restored).data, Operator(circuit).data)
    assert restored.data[1].operation.label == "matrix"
    assert restored.data[1].operation.base_class is UnitaryGate


def test_nonunitary_matrix_is_not_repaired_or_rejected_by_transport():
    matrix = np.array([[2, 0], [0, 0]], dtype=complex)
    circuit = QuantumCircuit(1)
    circuit.append(UnitaryGate(matrix, check_input=False), [0])
    restored = decode_circuit(encode_circuit(circuit))
    np.testing.assert_array_equal(restored.data[0].operation.params[0], matrix)
    assert not Operator(restored).is_unitary()


def test_labels_on_standard_singletons_survive_without_mutating_singleton():
    circuit = QuantumCircuit(1)
    circuit.x(0, label="custom X")
    restored = decode_circuit(encode_circuit(circuit))
    assert restored.data[0].operation.label == "custom X"
    from qiskit.circuit.library import XGate

    assert XGate().label is None


@pytest.mark.parametrize("mutation", ["shape", "arity", "label", "allocation"])
def test_malformed_matrix_payload_rejected(mutation):
    circuit = QuantumCircuit(1)
    circuit.unitary(np.eye(2), [0])
    wire = encode_circuit(circuit)
    op = wire["operations"][0]
    if mutation == "shape":
        op["params"][0]["shape"] = [1, 4]
    elif mutation == "arity":
        op["qubits"] = []
    elif mutation == "label":
        op["label"] = {"constructor": "untrusted"}
    else:
        wire["operations"] = [copy.deepcopy(op) for _ in range(8193)]
    with pytest.raises(WireError):
        decode_circuit(wire)

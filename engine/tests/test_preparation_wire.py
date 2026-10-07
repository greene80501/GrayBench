import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import StatePreparation
from qiskit.exceptions import QiskitError
from qiskit.quantum_info import Operator, Statevector

from graybench.circuit_wire import WireError, decode_circuit, encode_circuit


def roundtrip(op):
    circuit = QuantumCircuit(op.num_qubits)
    circuit.append(op, list(reversed(range(op.num_qubits))))
    return decode_circuit(encode_circuit(circuit)), circuit


@pytest.mark.parametrize("inverse", [False, True])
@pytest.mark.parametrize(
    "value", ["r+", 2, [0.5, 0.5j, -0.5, -0.5j], np.array([0, 1j]), Statevector([1, 0])]
)
def test_preparation_modes_and_inverse_preserve_operator(value, inverse):
    op = StatePreparation(
        value, num_qubits=3 if type(value) is int else None, inverse=inverse, label="prep"
    )
    restored, original = roundtrip(op)
    np.testing.assert_allclose(Operator(restored).data, Operator(original).data, atol=1e-12)
    result = restored.data[0].operation
    assert result.label == op.label
    assert result.base_class is StatePreparation
    assert type(result._params_arg) is type(op._params_arg)
    # The pinned SDK's integer inverse loses num_qubits. Preserve that behavior too,
    # rather than claiming a corrected inverse is an identical representation.
    np.testing.assert_allclose(
        Operator(result.inverse()).data, Operator(op.inverse()).data, atol=1e-12
    )


def test_normalized_input_retains_original_argument_and_inverse_failure():
    op = StatePreparation([2, 0], normalize=True)
    restored, original = roundtrip(op)
    np.testing.assert_allclose(Operator(restored).data, Operator(original).data)
    result = restored.data[0].operation
    assert result._params_arg == [2, 0]
    assert result.params == op.params
    for item in (op, result):
        with pytest.raises(QiskitError):
            item.inverse()


def test_modified_non_normalized_parameters_are_not_repaired():
    op = StatePreparation([1, 0])
    op.params = [2, 0]
    op.label = None
    restored, _ = roundtrip(op)
    result = restored.data[0].operation
    assert result.params == op.params
    assert result._params_arg == [1, 0]
    assert result.label is None


@pytest.mark.parametrize(
    "mutation", ["nested", "nested_array", "flags", "mode", "inverse", "dimensions", "constructor"]
)
def test_untrusted_preparation_records_are_bounded(mutation):
    circuit = QuantumCircuit(1)
    circuit.append(StatePreparation([1, 0]), [0])
    wire = encode_circuit(circuit)
    op = wire["operations"][0]
    record = op["params"][0]
    if mutation == "nested":
        record["original"] = {"kind": "list", "items": [record["original"]]}
    elif mutation == "nested_array":
        record["original"] = {"kind": "list", "items": [{"kind": "ndarray_v1"}]}
    elif mutation == "flags":
        record["inverse"] = 1
    elif mutation == "mode":
        record["from_int"] = True
    elif mutation == "inverse":
        record["inverse"] = True
    elif mutation == "dimensions":
        op["qubits"] = []
    else:
        record["original"] = {"kind": "circuit_v4"}
    with pytest.raises(WireError):
        decode_circuit(wire)

import copy

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Gate, Instruction, Parameter
from qiskit.circuit.library import XGate
from qiskit.quantum_info import Operator

from graybench.circuit_wire import WireError
from graybench.value_wire import decode, encode


def test_nested_generic_gate_preserves_definition_parameters_names_and_metadata():
    angle = Parameter("angle")
    inner = QuantumCircuit(1, name="inner")
    inner.ry(angle, 0)
    inner.metadata = {"note": [True, 2, 0.5, None]}
    gate = inner.to_gate(label="rotation")
    outer = QuantumCircuit(1, name="outer")
    outer.append(gate, [0])
    outer.global_phase = angle / 2
    restored = decode(encode(outer))
    operation = restored.data[0].operation
    assert type(operation) is Gate
    assert operation.name == gate.name and operation.label == gate.label
    assert operation.definition.name == gate.definition.name
    assert operation.definition.metadata == gate.definition.metadata
    assert operation.params == gate.params
    np.testing.assert_allclose(
        Operator(restored.assign_parameters({angle: 0.7})).data,
        Operator(outer.assign_parameters({angle: 0.7})).data,
    )


def test_plain_instruction_retains_classical_definition():
    circuit = QuantumCircuit(2, 2, name="bell_instruction")
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    original = circuit.to_instruction()
    restored = decode(encode(original))
    assert type(restored) is Instruction
    assert restored.name == original.name
    assert restored.num_clbits == 2
    assert restored.definition == original.definition


@pytest.mark.parametrize("name", ["", "h", "delay", "barrier", "unitary"])
def test_generic_gate_name_is_not_interpreted_as_a_standard_constructor(name):
    definition = QuantumCircuit(1)
    definition.x(0)
    gate = Gate(name, 1, [])
    gate.definition = definition
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0])
    restored = decode(encode(circuit))
    assert type(restored.data[0].operation) is Gate
    np.testing.assert_allclose(Operator(restored).data, Operator(circuit).data)


def test_recursive_definition_is_bounded_during_encoding():
    gate = Gate("recursive", 1, [])
    definition = QuantumCircuit(1)
    definition.append(gate, [0], copy=False)
    gate.definition = definition
    with pytest.raises(WireError, match="nesting"):
        encode(gate)


def test_customized_standard_definition_is_not_silently_discarded():
    gate = XGate().to_mutable()
    definition = QuantumCircuit(1)
    definition.h(0)
    gate.definition = definition
    with pytest.raises(WireError, match="Customized standalone"):
        encode(gate)


@pytest.mark.parametrize("mutable", [False, True])
def test_standalone_standard_gate_encoding_is_stable_and_retains_mutability(mutable):
    original = XGate().to_mutable() if mutable else XGate()
    before = encode(original)
    restored = decode(before)
    assert restored.mutable == mutable
    assert encode(restored) == before


@pytest.mark.parametrize("change", ["class", "qubits", "extra", "nested"])
def test_malformed_instruction_definitions_rejected(change):
    circuit = QuantumCircuit(1)
    circuit.x(0)
    record = encode(circuit.to_gate())
    if change == "class":
        record["class"] = "ArbitraryConstructor"
    elif change == "qubits":
        record["qubits"] = 2
    elif change == "extra":
        record["execute"] = "print('not code')"
    else:
        for _ in range(10):
            wrapper = copy.deepcopy(record["definition"])
            wrapper["operations"] = [
                {
                    "name": "__generic_definition_v1__",
                    "params": [record],
                    "qubits": [0],
                    "clbits": [],
                    "unit": None,
                    "label": None,
                }
            ]
            record = {**record, "definition": wrapper}
    with pytest.raises(WireError):
        decode(record)


@pytest.mark.parametrize(
    "metadata", [{1: "would coerce"}, {"tuple": (1, 2)}, {"value": float("nan")}]
)
def test_metadata_is_not_silently_coerced(metadata):
    circuit = QuantumCircuit(1)
    circuit.metadata = metadata
    with pytest.raises(WireError):
        encode(circuit)


def test_nested_instruction_record_has_a_checked_type():
    circuit = QuantumCircuit(1)
    circuit.x(0)
    wrapper = QuantumCircuit(1)
    wrapper.append(circuit.to_gate(), [0])
    record = encode(wrapper)
    record["operations"][0]["params"][0] = []
    with pytest.raises(WireError, match="instruction record"):
        decode(record)

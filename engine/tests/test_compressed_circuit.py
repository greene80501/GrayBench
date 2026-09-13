import base64
import zlib

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from graybench.circuit_wire import WireError
from graybench.value_wire import decode, encode


def test_large_circuit_compression_preserves_every_instruction_and_operator():
    circuit = QuantumCircuit(1)
    for _ in range(2500):
        circuit.h(0)
        circuit.t(0)
    wire = encode(circuit)
    assert wire["kind"] == "compressed_circuit_v1"
    assert len(wire["bytes"]) < wire["size"] / 10
    restored = decode(wire)
    assert list(restored.data) == list(circuit.data)
    np.testing.assert_allclose(Operator(restored).data, Operator(circuit).data)


@pytest.mark.parametrize("mutation", ["tiny_size", "oversize", "trailing", "truncated", "base64"])
def test_malformed_compressed_stream_rejected(mutation):
    circuit = QuantumCircuit(1)
    for _ in range(1000):
        circuit.x(0)
    wire = encode(circuit)
    if mutation == "tiny_size":
        wire["size"] = 1
    elif mutation == "oversize":
        wire["size"] = 64 * 1024 * 1024 + 1
    elif mutation == "trailing":
        wire["bytes"] = base64.b64encode(
            base64.b64decode(wire["bytes"]) + zlib.compress(b"extra")
        ).decode()
    elif mutation == "truncated":
        wire["bytes"] = wire["bytes"][:-4]
    else:
        wire["bytes"] = "!invalid!"
    with pytest.raises(WireError):
        decode(wire)

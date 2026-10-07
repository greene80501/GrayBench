"""Identify the canonical family-116 matrix owner in the adapted runtime."""

import json

import numpy as np
from qiskit.circuit.library import HamiltonianGate, PauliEvolutionGate
from qiskit.quantum_info import Pauli
from qiskit.synthesis import MatrixExponential

operation = MatrixExponential().synthesize(PauliEvolutionGate(Pauli("X"), 1.0)).data[
    0
].operation
assert type(operation) is HamiltonianGate
matrix = operation.params[0]
assert type(matrix) is np.ndarray and matrix.shape == (2, 2)
base = matrix.base
assert type(base) is np.ndarray and base.shape == (4,)
owner = base.base
assert type(owner).__name__ == "PySliceContainer"
try:
    memoryview(owner)
except TypeError:
    buffer_exported = False
else:
    buffer_exported = True
assert not buffer_exported
print(
    json.dumps(
        {
            "operation": type(operation).__name__,
            "matrix_shape": matrix.shape,
            "matrix_dtype": matrix.dtype.str,
            "matrix_owns_data": matrix.flags.owndata,
            "base_shape": base.shape,
            "base_owns_data": base.flags.owndata,
            "owner_type": type(owner).__name__,
            "owner_module": type(owner).__module__,
            "owner_buffer_exported": buffer_exported,
        },
        sort_keys=True,
    ),
    flush=True,
)

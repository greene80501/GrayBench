"""Adapted runtime: cached Hamiltonian definition and live matrix aliases."""

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import HamiltonianGate

from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_limits import GraphLimits
from graybench.graph_wire import GraphArena

registry = PublicAnchorRegistry.capture()
source, target = tuple(
    GraphArena(side=side, session="native-hamiltonian", limits=GraphLimits(), anchors=registry)
    for side in ("judge", "candidate")
)
gate = HamiltonianGate(np.array([[0, 1], [1, 0]], dtype=complex), 0.3)
definition = gate.definition
circuit = QuantumCircuit(1)
circuit.append(gate, [0], copy=False)
matrix = gate.params[0]
matrix[0, 1] = 0.2
wire = source.snapshot({"value": (circuit, gate, matrix, vars(gate), definition)}, sequence=1)
remote, operation, array, attrs, body = target.commit(target.prepare(wire, sequence=1))["value"]
assert type(operation) is HamiltonianGate
assert remote.data[0].operation is operation
assert vars(operation) is attrs and operation.params[0] is array
assert operation._definition is body
assert array[0, 1] == 0.2 and array[1, 0] == 1
array[1, 0] = 0.4
wire = target.snapshot({"value": (operation, array)}, sequence=1)
restored, returned_matrix = source.commit(source.prepare(wire, sequence=1))["value"]
assert restored is gate and returned_matrix is matrix
assert matrix[1, 0] == 0.4 and gate._definition is definition
print("Hamiltonian cached definition and native matrix aliases passed")

import os

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Delay
from qiskit.circuit.library import LinearFunction, StatePreparation, UnitaryGate
from qiskit.converters import circuit_to_dag, dag_to_circuit

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="special-instructions", limits=GraphLimits())
        for s in ("judge", "candidate")
    )


def transfer(a, b, value, sequence=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=sequence), sequence=sequence))[
        "value"
    ]


def test_linear_function_keeps_shared_matrix_and_raw_definition():
    a, b = arenas()
    gate = LinearFunction(np.eye(2, dtype=bool))
    qc = QuantumCircuit(2)
    qc.append(gate, [0, 1], copy=False)
    remote, op, matrix, attrs = transfer(a, b, (qc, gate, gate.params[0], vars(gate)))
    assert type(op) is LinearFunction and vars(op) is attrs
    assert remote.data[0].operation is op
    assert remote.data[0].params[0] is op.params[0] is matrix
    assert op._definition is gate._definition is None
    matrix[0, 1] = True
    assert transfer(b, a, remote) is qc and bool(gate.params[0][0, 1])


@pytest.mark.parametrize("mode", ["label", "integer", "list", "array"])
def test_state_preparation_keeps_original_argument_and_cached_params(mode):
    a, b = arenas()
    argument = {"label": "01", "integer": 1, "list": [1, 0], "array": np.array([1, 0])}[mode]
    gate = StatePreparation(argument, **({"num_qubits": 2} if mode == "integer" else {}))
    qc = QuantumCircuit(gate.num_qubits)
    qc.append(gate, qc.qubits, copy=False)
    remote, op, params, arg = transfer(a, b, (qc, gate, gate.params, gate._params_arg))
    assert type(op) is StatePreparation and op.params is params
    if mode in ("list", "array"):
        assert op._params_arg is arg
    assert remote.data[0].operation is op
    assert (op._from_int, op._from_label, op._inverse) == (
        gate._from_int,
        gate._from_label,
        gate._inverse,
    )
    assert op._definition is gate._definition is None
    before = list(remote.data[0].params)
    params[0] = 0
    assert list(remote.data[0].params) == before
    assert transfer(b, a, op) is gate and gate.params[0] == 0


def test_delay_keeps_cached_unit_separate_from_mutated_operation():
    a, b = arenas()
    gate = Delay(12, "dt")
    qc = QuantumCircuit(1)
    qc.append(gate, [0], copy=False)
    gate.unit = "ns"
    gate.duration = 23
    remote, op, attrs = transfer(a, b, (qc, gate, vars(gate)))
    assert type(op) is Delay and vars(op) is attrs
    assert remote.data[0].operation is op
    assert op.unit == "ns" and op.duration == 23
    native = dag_to_circuit(circuit_to_dag(remote))
    assert native.data[0].operation.unit == "dt"
    assert native.data[0].params == [12]
    op.unit = "us"
    assert transfer(b, a, remote) is qc
    assert gate.unit == "us" and gate.duration == 23
    native = dag_to_circuit(circuit_to_dag(qc))
    assert native.data[0].operation.unit == "dt"
    assert native.data[0].params == [12]


def test_unitary_keeps_intrinsic_matrix_separate_from_mutated_python_params():
    a, b = arenas()
    gate = UnitaryGate(np.eye(2))
    qc = QuantumCircuit(1)
    qc.append(gate, [0], copy=False)
    gate.params[0] = np.array([[0, 1], [1, 0]], dtype=complex)
    remote, op, matrix = transfer(a, b, (qc, gate, gate.params[0]))
    assert type(op) is UnitaryGate and remote.data[0].operation is op
    assert op.params[0] is matrix
    np.testing.assert_array_equal(matrix, [[0, 1], [1, 0]])
    assert remote.data[0].params == []
    np.testing.assert_array_equal(remote.data[0].matrix, np.eye(2))
    assert transfer(b, a, remote) is qc
    np.testing.assert_array_equal(qc.data[0].matrix, np.eye(2))
    np.testing.assert_array_equal(gate.params[0], [[0, 1], [1, 0]])


@pytest.mark.parametrize("limit", ["array_bytes", "matrix_bytes"])
def test_unitary_intrinsic_matrices_share_graph_storage_budget(limit):
    gate = UnitaryGate(np.eye(2))
    qc = QuantumCircuit(1)
    qc.append(gate, [0], copy=False)
    qc.append(gate, [0], copy=False)
    # Two independent native complex128 matrices plus one Python owner matrix.
    arena = GraphArena(side="judge", session="budget", limits=GraphLimits(**{limit: 127}))
    with pytest.raises(WireLimitError):
        arena.snapshot({"value": qc}, sequence=1)


@pytest.mark.parametrize("kind", ["delay", "unitary"])
def test_native_instruction_keeps_fresh_wrapper_behavior(kind):
    a, b = arenas()
    qc = QuantumCircuit(1)
    gate = Delay(17, "ns") if kind == "delay" else UnitaryGate(np.eye(2))
    gate.label = "native-label"
    qc.append(gate, [0])
    qc = dag_to_circuit(circuit_to_dag(qc))
    assert qc.data[0].operation is not qc.data[0].operation
    remote = transfer(a, b, qc)
    assert remote.data[0].label == qc.data[0].label == "native-label"
    assert remote.data[0].operation is not remote.data[0].operation
    if kind == "delay":
        assert remote.data[0].operation.unit == "ns" and remote.data[0].params == [17]
    else:
        assert remote.data[0].params == []
        np.testing.assert_array_equal(remote.data[0].matrix, np.eye(2))
    assert transfer(b, a, remote) is qc
    assert qc.data[0].operation is not qc.data[0].operation


@pytest.mark.parametrize("field,value", [("shape", [4, 1]), ("dtype", "|O"), ("bytes", "bad")])
def test_invalid_intrinsic_matrix_rejected_before_existing_circuit_mutation(field, value):
    a, b = arenas()
    qc = QuantumCircuit(1)
    qc.append(UnitaryGate(np.eye(2)), [0])
    remote = transfer(a, b, qc)
    wire = a.snapshot({"value": qc}, sequence=2)
    data = next(n for n in wire["nodes"] if n["kind"] == "circuit_data")
    data["state"]["operations"][0]["matrix"][field] = value
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    np.testing.assert_array_equal(remote.data[0].matrix, np.eye(2))


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Immutable image required")
def test_protected_special_instructions_preserve_both_native_and_python_state():
    from test_graph_bridge import judge

    result = judge(
        """import numpy as np
from qiskit.converters import circuit_to_dag, dag_to_circuit
def check(candidate):
    qc, unitary, delay, linear, prep = candidate()
    assert qc.data[0].operation is unitary
    assert qc.data[1].operation is delay
    assert qc.data[2].operation is linear
    assert qc.data[3].operation is prep
    np.testing.assert_array_equal(qc.data[0].matrix, np.eye(2))
    np.testing.assert_array_equal(unitary.params[0], [[0,1],[1,0]])
    assert delay.unit == 'ns' and delay.duration == 23
    native = dag_to_circuit(circuit_to_dag(qc))
    assert native.data[1].operation.unit == 'dt'
    assert native.data[1].params == [12]
    assert prep._definition is None and linear._definition is None
""",
        """import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Delay
from qiskit.circuit.library import UnitaryGate, LinearFunction, StatePreparation
def answer():
    qc = QuantumCircuit(1)
    ops = [UnitaryGate(np.eye(2)), Delay(12,'dt'),
           LinearFunction(np.eye(1,dtype=bool)), StatePreparation([1,0])]
    for op in ops: qc.append(op,[0],copy=False)
    ops[0].params[0] = np.array([[0,1],[1,0]],dtype=complex)
    ops[1].unit = 'ns'
    ops[1].duration = 23
    return (qc,*ops)
""",
    )
    assert result.outcome == "pass", result

import os

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import HamiltonianGate
from test_graph_converted_instructions import arenas, transfer


@pytest.mark.parametrize("cached", [False, True])
def test_hamiltonian_raw_matrix_alias_and_definition_are_preserved(cached):
    if cached:
        from scipy.linalg import _internal_matfuncs

        if not hasattr(_internal_matfuncs, "_graybench_storage_view"):
            pytest.skip("Cached definition requires the experimental registered-storage image")
    source, target = arenas()
    gate = HamiltonianGate(np.array([[0, 1], [1, 0]], dtype=complex), 0.3)
    definition = gate.definition if cached else None
    circuit = QuantumCircuit(1)
    circuit.append(gate, [0], copy=False)
    matrix = gate.params[0]
    matrix[0, 1] = 0.2  # Deliberately non-Hermitian: transport must not repair it.
    remote, operation, array, attrs, body = transfer(
        source, target, (circuit, gate, matrix, vars(gate), definition)
    )
    assert type(operation) is HamiltonianGate
    assert remote.data[0].operation is operation
    assert vars(operation) is attrs and operation.params[0] is array
    assert operation._definition is body
    assert array[0, 1] == 0.2 and array[1, 0] == 1
    array[1, 0] = 0.4
    restored, returned_matrix = transfer(target, source, (operation, array))
    assert restored is gate and returned_matrix is matrix
    assert matrix[1, 0] == 0.4 and gate._definition is definition


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
@pytest.mark.parametrize("transport", ["snapshot-v1", "delta-v1"])
@pytest.mark.parametrize("wrong_time", [False, True])
def test_protected_hamiltonian_matrix_and_cached_definition(transport, wrong_time):
    from test_graph_bridge import task

    from graybench.upstream import UpstreamJudge

    check = """import numpy as np
from qiskit.quantum_info import Operator
from qiskit import QuantumCircuit
def check(candidate):
    gate, matrix = candidate()
    assert gate.params[0] is matrix and gate._definition is None
    expected = QuantumCircuit(1)
    expected.rx(0.6, 0)
    np.testing.assert_allclose(Operator(gate).data, Operator(expected).data, atol=1e-12)
    cached = gate.definition
    matrix[:] = 0
    returned = candidate(gate)
    assert returned is gate and gate.params[0] is matrix and gate._definition is cached
    np.testing.assert_allclose(Operator(gate).data, np.eye(2), atol=1e-12)
    np.testing.assert_allclose(Operator(cached).data, Operator(expected).data, atol=1e-12)
"""
    code = """import numpy as np
from qiskit.circuit.library import HamiltonianGate
held = None
def answer(gate=None):
    global held
    if gate is not None:
        assert gate is held and gate._definition is not None
        assert np.all(gate.params[0] == 0)
        return gate
    held = HamiltonianGate(np.array([[0,1],[1,0]],dtype=complex), TIME)
    return held, held.params[0]
""".replace("TIME", "0" if wrong_time else "0.3")
    result = UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
        graph_transport=transport,
    ).evaluate(task(check), code)
    assert result.outcome == ("fail" if wrong_time else "pass"), result.evidence.get("stderr")

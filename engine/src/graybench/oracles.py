"""Trusted semantic checks; these functions and expectations never enter candidate execution."""


def bell_file_circuits(circuits) -> dict:
    """Task 82 semantic track: first serialized circuit prepares Phi+, up to global phase."""
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    if type(circuits) is not list or not circuits:
        return {"passed": False, "reason": "expected at least one serialized circuit"}
    circuit = circuits[0]
    if not isinstance(circuit, QuantumCircuit) or circuit.num_qubits != 2:
        return {"passed": False, "reason": "expected a two-qubit circuit"}
    try:
        state = Statevector.from_instruction(circuit).data
    except Exception as exc:
        return {
            "passed": False,
            "reason": "not a pure state preparation",
            "exception": type(exc).__name__,
        }
    expected = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    fidelity = float(abs(np.vdot(expected, state)) ** 2)
    return {
        "passed": bool(np.isclose(fidelity, 1.0, atol=1e-10, rtol=0)),
        "state_fidelity": fidelity,
        "serialized_circuit_count": len(circuits),
        "oracle": "task82-bell-file-state-v1",
    }


def ghz_custom_layout(circuit) -> dict:
    """Task 20's strengthened semantic check, distinct from the upstream shape-only oracle.

    Check a pure GHZ+ state over the three routed logical outputs, up to global phase,
    with all ancillary output qubits in zero. Do not assume routing preserves physical positions.
    This verifies returned circuit behavior, not the unobservable pass-manager algorithm used.
    """
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    if not isinstance(circuit, QuantumCircuit):
        return {"passed": False, "reason": "expected QuantumCircuit"}
    if circuit.num_qubits != 7 or circuit.layout is None:
        return {"passed": False, "reason": "expected seven-qubit mapped circuit"}
    initial = circuit.layout.initial_index_layout()
    if initial[:3] != [2, 4, 6]:
        return {"passed": False, "reason": "incorrect initial logical layout"}
    final = circuit.layout.final_index_layout()
    if len(final) != 3 or len(set(final)) != 3 or any(not 0 <= i < 7 for i in final):
        return {"passed": False, "reason": "invalid final logical layout"}
    candidate = circuit.remove_final_measurements(inplace=False)
    try:
        state = Statevector.from_instruction(candidate).data
    except Exception as exc:
        return {
            "passed": False,
            "reason": "circuit cannot be evaluated as a state preparation",
            "exception": type(exc).__name__,
        }
    expected = np.zeros(128, dtype=complex)
    expected[0] = 1 / np.sqrt(2)
    expected[sum(1 << i for i in final)] = 1 / np.sqrt(2)
    fidelity = float(abs(np.vdot(expected, state)) ** 2)
    return {
        "passed": bool(np.isclose(fidelity, 1.0, atol=1e-10, rtol=0)),
        "state_fidelity": fidelity,
        "final_logical_positions": final,
        "oracle": "task20-ghz-state-v1",
        "algorithm_requirement": "not_proven_by_return_value",
    }

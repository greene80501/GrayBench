"""Exact pinned public/check records for the Task 11 revision ancestry."""

SOURCE_RECORDS = {
    "normal": {
        "digest": "58c14e6033e5eaf0855b3e221ae361107494e70e3f6a0ac9affe7115c9b27bf5",
        "prompt": "from qiskit import QuantumCircuit\n"
        "from qiskit.quantum_info import Statevector\n"
        "def get_statevector(circuit: QuantumCircuit) -> Statevector:\n"
        '    """ Return the statevector from a circuit.\n'
        '    """',
        "test": "def check(candidate):\n"
        "    test_circuit = QuantumCircuit(2)\n"
        "    test_circuit.u(0.39702, 0.238798, 0.298374, 0)\n"
        "    test_circuit.cx(0, 1)\n"
        "\n"
        "    result = candidate(test_circuit)\n"
        '    assert isinstance(result, Statevector), f"Expected Statevector '
        'instance, got {type(result).__name__}"\n'
        "    assert Statevector.from_instruction(test_circuit).equiv(result), "
        '"Quantum states or operators are not equivalent"\n',
    },
    "hard": {
        "digest": "980244496340c9bf363e39cd2b2f714b587936c8a710c6b846d4592a24b4236f",
        "prompt": "Return the statevector from a circuit.\n"
        "You must implement this using a function named `get_statevector` with "
        "the following arguments: circuit.",
        "test": "from qiskit import QuantumCircuit\n"
        "from qiskit.quantum_info import Statevector\n"
        "def check(candidate):\n"
        "    test_circuit = QuantumCircuit(2)\n"
        "    test_circuit.u(0.39702, 0.238798, 0.298374, 0)\n"
        "    test_circuit.cx(0, 1)\n"
        "\n"
        "    result = candidate(test_circuit)\n"
        '    assert isinstance(result, Statevector), f"Expected Statevector '
        'instance, got {type(result).__name__}"\n'
        "    assert Statevector.from_instruction(test_circuit).equiv(result), "
        '"Quantum states or operators are not equivalent"\n'
        "\n"
        "check(get_statevector)",
    },
}

"""Exact source bytes for explicitly revised matrix-semantics tasks."""

SOURCE_RECORDS = {
    (116, "hard"): {
        "digest": "548733e9c66ce4a782794d7cd3aeff29e38624e563f6eedd102c9479d320f2a6",
        "prompt": "Synthesize an evolution gate using MatrixExponential for a given Pauli "
        "string and time.\n"
        "The Pauli string can be any combination of 'I', 'X', 'Y', and 'Z'.\n"
        "Return the resulting QuantumCircuit.\n"
        "You must implement this using a function named "
        "`synthesize_evolution_gate` with the following arguments: "
        "pauli_string, time.",
        "test": "from qiskit.circuit.library import PauliEvolutionGate\n"
        "from qiskit.synthesis import MatrixExponential\n"
        "from qiskit import QuantumCircuit\n"
        "from qiskit.quantum_info import Pauli, Operator\n"
        "import numpy as np\n"
        "def check(candidate):\n"
        '    pauli_string = "X"\n'
        "    time = 1.0\n"
        "    \n"
        "    qc = candidate(pauli_string, time)\n"
        '    assert isinstance(qc, QuantumCircuit), "The function should return a '
        'QuantumCircuit"\n'
        '    assert qc.size() > 0, "The circuit should not be empty"\n'
        "    \n"
        "    ideal_solution = QuantumCircuit(1)\n"
        "    ideal_solution.rx(2 * time, 0)\n"
        "    \n"
        '    assert np.allclose(Operator(qc), Operator(ideal_solution)), "The '
        'synthesized circuit does not match the expected evolution"\n'
        "\n"
        "check(synthesize_evolution_gate)",
    },
    (116, "normal"): {
        "digest": "e91d1fdee6400859d41d0ec5ba98da055ebd8978f3ef0a63c555b858fc3a151c",
        "prompt": "from qiskit.circuit.library import PauliEvolutionGate\n"
        "from qiskit.synthesis import MatrixExponential\n"
        "from qiskit import QuantumCircuit\n"
        "from qiskit.quantum_info import Pauli, Operator\n"
        "import numpy as np\n"
        "def synthesize_evolution_gate(pauli_string: str, time: float) -> "
        "QuantumCircuit:\n"
        '    """ Synthesize an evolution gate using MatrixExponential for a '
        "given Pauli string and time.\n"
        "    The Pauli string can be any combination of 'I', 'X', 'Y', and "
        "'Z'.\n"
        "    Return the resulting QuantumCircuit.\n"
        '    """',
        "test": "def check(candidate):\n"
        '    pauli_string = "X"\n'
        "    time = 1.0\n"
        "    \n"
        "    qc = candidate(pauli_string, time)\n"
        '    assert isinstance(qc, QuantumCircuit), "The function should return '
        'a QuantumCircuit"\n'
        '    assert qc.size() > 0, "The circuit should not be empty"\n'
        "    \n"
        "    ideal_solution = QuantumCircuit(1)\n"
        "    ideal_solution.rx(2 * time, 0)\n"
        "    \n"
        '    assert np.allclose(Operator(qc), Operator(ideal_solution)), "The '
        'synthesized circuit does not match the expected evolution"\n',
    },
    (120, "hard"): {
        "digest": "664c1c740b6ee44cd7a4c11522c7b39c15e983237304e015adb787d839f53bfb",
        "prompt": "Create a QuantumCircuit with a Diagonal gate applied to the qubits.\n"
        "The diagonal elements are provided in the list 'diag'.\n"
        "You must implement this using a function named "
        "`create_diagonal_circuit` with the following arguments: diag.",
        "test": "from qiskit.circuit.library import Diagonal\n"
        "from qiskit import QuantumCircuit\n"
        "from qiskit.quantum_info import Operator\n"
        "def check(candidate):\n"
        "    diag = [1, 1j, -1, -1j]\n"
        "    qc = candidate(diag)\n"
        '    assert isinstance(qc, QuantumCircuit), "The function should return a '
        'QuantumCircuit"\n'
        "    \n"
        "    op_circuit = Operator(qc)\n"
        "    \n"
        "    expected_diagonal = Diagonal(diag)\n"
        "    op_expected = Operator(expected_diagonal)\n"
        "    \n"
        '    assert op_circuit.equiv(op_expected), "The circuit does not match '
        'the expected Diagonal gate"\n'
        "\n"
        "check(create_diagonal_circuit)",
    },
    (120, "normal"): {
        "digest": "fd4704a010c3b682442a8c0ef5e468d8b5483a98843e65a17043bc075be60d90",
        "prompt": "from qiskit.circuit.library import Diagonal\n"
        "from qiskit import QuantumCircuit\n"
        "from qiskit.quantum_info import Operator\n"
        "def create_diagonal_circuit(diag: list) -> QuantumCircuit:\n"
        '    """ Create a QuantumCircuit with a Diagonal gate applied to the '
        "qubits.\n"
        "    The diagonal elements are provided in the list 'diag'.\n"
        '    """',
        "test": "def check(candidate):\n"
        "    diag = [1, 1j, -1, -1j]\n"
        "    qc = candidate(diag)\n"
        '    assert isinstance(qc, QuantumCircuit), "The function should return '
        'a QuantumCircuit"\n'
        "    \n"
        "    op_circuit = Operator(qc)\n"
        "    \n"
        "    expected_diagonal = Diagonal(diag)\n"
        "    op_expected = Operator(expected_diagonal)\n"
        "    \n"
        '    assert op_circuit.equiv(op_expected), "The circuit does not match '
        'the expected Diagonal gate"\n',
    },
    (125, "hard"): {
        "digest": "8af190241144f88d18bb8520425d0e18f6ba8d909b08a003af3ad58981069a4e",
        "prompt": "Given a QuantumCircuit, convert it into a gate equivalent to the "
        "action of the input circuit and return it.\n"
        "You must implement this using a function named `circ_to_gate` with the "
        "following arguments: circ.",
        "test": "from qiskit.converters import circuit_to_gate\n"
        "def check(candidate):\n"
        "    from qiskit import QuantumCircuit, QuantumRegister\n"
        "    from qiskit.circuit.gate import Gate\n"
        "    from qiskit.quantum_info import Operator\n"
        "    from qiskit.circuit.library import ZGate\n"
        '    q = QuantumRegister(3, "q")\n'
        "    circ = QuantumCircuit(q)\n"
        "    circ.h(q[0])\n"
        "    circ.cx(q[0], q[1])\n"
        "    custom_gate = candidate(circ)\n"
        '    assert type(custom_gate) == Gate, f"Expected Gate, got '
        '{type(custom_gate).__name__}"\n'
        '    assert custom_gate.num_qubits == 3, f"Expected 3 qubits, got '
        '{custom_gate.num_qubits}"\n'
        '    assert custom_gate.num_clbits == 0, f"Expected 0 classical bits, got '
        '{custom_gate.num_clbits}"\n'
        "\n"
        '    q = QuantumRegister(1, "q")\n'
        "    circ = QuantumCircuit(q)\n"
        "    circ.h(q)\n"
        "    circ.x(q)\n"
        "    circ.h(q)\n"
        "    hxh_gate = candidate(circ)\n"
        "    hxh_op = Operator(hxh_gate)\n"
        "    z_op = Operator(ZGate())\n"
        '    assert hxh_op.equiv(z_op), "Quantum states or operators are not '
        'equivalent"\n'
        "\n"
        "check(circ_to_gate)",
    },
    (125, "normal"): {
        "digest": "c841a3d4c550728239b15f4925deda88fb4434943373aa2ced2eea07ac662d9e",
        "prompt": "from qiskit.converters import circuit_to_gate\n"
        "def circ_to_gate(circ):\n"
        '    """ Given a QuantumCircuit, convert it into a gate equivalent to '
        "the action of the input circuit and return it.\n"
        '    """',
        "test": "def check(candidate):\n"
        "    from qiskit import QuantumCircuit, QuantumRegister\n"
        "    from qiskit.circuit.gate import Gate\n"
        "    from qiskit.quantum_info import Operator\n"
        "    from qiskit.circuit.library import ZGate\n"
        '    q = QuantumRegister(3, "q")\n'
        "    circ = QuantumCircuit(q)\n"
        "    circ.h(q[0])\n"
        "    circ.cx(q[0], q[1])\n"
        "    custom_gate = candidate(circ)\n"
        '    assert type(custom_gate) == Gate, f"Expected Gate, got '
        '{type(custom_gate).__name__}"\n'
        '    assert custom_gate.num_qubits == 3, f"Expected 3 qubits, got '
        '{custom_gate.num_qubits}"\n'
        '    assert custom_gate.num_clbits == 0, f"Expected 0 classical bits, '
        'got {custom_gate.num_clbits}"\n'
        "\n"
        '    q = QuantumRegister(1, "q")\n'
        "    circ = QuantumCircuit(q)\n"
        "    circ.h(q)\n"
        "    circ.x(q)\n"
        "    circ.h(q)\n"
        "    hxh_gate = candidate(circ)\n"
        "    hxh_op = Operator(hxh_gate)\n"
        "    z_op = Operator(ZGate())\n"
        '    assert hxh_op.equiv(z_op), "Quantum states or operators are not '
        'equivalent"\n',
    },
}

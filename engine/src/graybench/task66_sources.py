"""Exact pinned Task66 source ancestry; original scores stay unchanged."""

SOURCE_RECORDS = {
    "normal": {
        "digest": ("bae918da0932fdcc5522fdfff18a9a4c2b4092c0e02cf6896c4778edd32ea211"),
        "prompt": (
            "from qiskit import QuantumCircuit\n"
            "from numpy import arccos, sqrt\n"
            "def w_state()->QuantumCircuit:\n"
            '    """ Generate a Quantum Circuit for a W state and measure'
            " it.\n"
            '    """'
        ),
        "test": (
            "def check(candidate):\n"
            "    from qiskit_aer import AerSimulator\n"
            "    from qiskit.transpiler.preset_passmanagers import genera"
            "te_preset_pass_manager\n"
            "    from qiskit_ibm_runtime import Sampler\n"
            "    result = candidate()\n"
            '    assert isinstance(result, QuantumCircuit), f"Expected Qu'
            'antumCircuit instance, got {type(result).__name__}"\n'
            '    assert result.num_qubits == 3, f"Expected 3 qubits, got '
            '{result.num_qubits}"\n'
            "    backend = AerSimulator()\n"
            "    sampler = Sampler(mode=backend)\n"
            "    pass_manager = generate_preset_pass_manager(optimization"
            "_level=1, backend=backend)\n"
            "    isa_circuit = pass_manager.run(result)\n"
            "    job = sampler.run([isa_circuit]).result()\n"
            "    counts= job[0].data.meas.get_counts()\n"
            "    assert counts.keys() == {'001', '010' , '100'}, f\"Expect"
            "ed keys {'001', '010' , '100'}, got {set(result.keys())}\"\n"
            "    assert counts['001'] >= 300 and counts['001'] <= 400, \"V"
            'alue outside expected range"\n'
            "    assert counts['010'] >= 300 and counts['010'] <= 400, \"V"
            'alue outside expected range"\n'
            "    assert counts['100'] >= 300 and counts['100'] <= 400, \"V"
            'alue outside expected range"\n'
            "    assert counts['001'] + counts['010'] + counts['100'] == "
            "1024, f\"Expected {1024}, got {counts['001'] + counts['010'] "
            "+ counts['100']}\"\n"
        ),
    },
    "hard": {
        "digest": ("d5e8ffe3c153b6147ff2a24533653cbcddf815ab43bc157d5e10704d274db6be"),
        "prompt": (
            "Generate a Quantum Circuit for a W state and measure it.\n"
            "You must implement this using a function named `w_state` wit"
            "h no arguments."
        ),
        "test": (
            "from qiskit import QuantumCircuit\n"
            "from numpy import arccos, sqrt\n"
            "def check(candidate):\n"
            "    from qiskit_aer import AerSimulator\n"
            "    from qiskit.transpiler.preset_passmanagers import genera"
            "te_preset_pass_manager\n"
            "    from qiskit_ibm_runtime import Sampler\n"
            "    result = candidate()\n"
            '    assert isinstance(result, QuantumCircuit), f"Expected Qu'
            'antumCircuit instance, got {type(result).__name__}"\n'
            '    assert result.num_qubits == 3, f"Expected 3 qubits, got '
            '{result.num_qubits}"\n'
            "    backend = AerSimulator()\n"
            "    sampler = Sampler(mode=backend)\n"
            "    pass_manager = generate_preset_pass_manager(optimization"
            "_level=1, backend=backend)\n"
            "    isa_circuit = pass_manager.run(result)\n"
            "    job = sampler.run([isa_circuit]).result()\n"
            "    counts= job[0].data.meas.get_counts()\n"
            "    assert counts.keys() == {'001', '010' , '100'}, f\"Expect"
            "ed keys {'001', '010' , '100'}, got {set(result.keys())}\"\n"
            "    assert counts['001'] >= 300 and counts['001'] <= 400, \"V"
            'alue outside expected range"\n'
            "    assert counts['010'] >= 300 and counts['010'] <= 400, \"V"
            'alue outside expected range"\n'
            "    assert counts['100'] >= 300 and counts['100'] <= 400, \"V"
            'alue outside expected range"\n'
            "    assert counts['001'] + counts['010'] + counts['100'] == "
            "1024, f\"Expected {1024}, got {counts['001'] + counts['010'] "
            "+ counts['100']}\"\n"
            "\n"
            "check(w_state)"
        ),
    },
}

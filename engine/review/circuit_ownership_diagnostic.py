"""Trusted pinned-SDK ownership audit; never executes candidate code or pickle."""

import hashlib
import json
import platform
from pathlib import Path

import qiskit
from qiskit import QuantumCircuit, QuantumRegister
from qiskit._accelerate.circuit import CircuitData


def main():
    checks = []
    register = QuantumRegister(3, "audit")
    supplied = [register[0], register[1]]
    data = CircuitData(qubits=supplied)
    assert data.qubits is not supplied
    assert data.qubits is data.qubits
    assert data._qubit_indices is data._qubit_indices
    checks.append("constructor_copies_list_but_getters_retain_caches")

    old_list, old_map = data.qubits, data._qubit_indices
    data.clear()
    assert data.qubits is old_list and data._qubit_indices is old_map
    checks.append("clear_preserves_membership_caches")

    data.add_qubit(register[2])
    assert data.qubits is not old_list and data._qubit_indices is not old_map
    assert len(old_list) == len(old_map) == 2
    assert len(data.qubits) == len(data._qubit_indices) == 3
    checks.append("adding_bit_replaces_caches_and_retains_detached_old_values")

    old_list, old_map = data.qubits, data._qubit_indices
    data.replace_bits(qubits=list(old_list))
    assert data.qubits is not old_list and data._qubit_indices is not old_map
    assert data.qubits == old_list
    checks.append("equal_membership_replacement_still_changes_cache_identity")

    external = list(data.qubits)
    data.replace_bits(qubits=external)
    assert data.qubits is not external
    try:
        data.qubits = external
    except AttributeError:
        pass
    else:
        raise AssertionError("Unexpected writable qubits cache property")
    checks.append("replace_bits_does_not_adopt_existing_python_list")

    saved = data.__reduce_ex__(4)[2]
    external_map = dict(saved[2])
    data.__setstate__((*saved[:2], external_map, *saved[3:]))
    assert data._qubit_indices is not external_map
    checks.append("fixed_native_setstate_does_not_adopt_index_dictionary")

    circuit = QuantumCircuit(2)
    circuit.cx(0, 1)
    actual_list = circuit.qubits
    removed = actual_list.pop()
    assert len(circuit.qubits) == 1 and circuit.num_qubits == 2
    assert circuit.data[0].qubits[1] == removed
    assert len(circuit._data.copy_empty_like().qubits) == 2
    checks.append("cache_content_can_diverge_from_intrinsic_membership")

    bit = circuit.data[0].qubits[0]
    location = circuit.find_bit(bit)
    assert location is circuit._data._qubit_indices[bit]
    assert location.registers is circuit._data._qubit_indices[bit].registers
    checks.append("find_bit_returns_cached_location_and_nested_register_list")

    print(
        json.dumps(
            {
                "scope": "native_circuit_ownership_audit",
                "production_bridge_integrated": False,
                "python": platform.python_version(),
                "system": platform.system(),
                "qiskit": qiskit.__version__,
                "checks_passed": checks,
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

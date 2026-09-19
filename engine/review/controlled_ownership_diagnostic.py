"""Trusted pinned-SDK ownership audit; no model candidate or judge execution."""

import hashlib
import json
import platform
from pathlib import Path

import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit import ControlledGate
from qiskit.circuit.library import CRXGate, CXGate, MCXGate, RXGate, XGate


def main():
    checks = []
    gate = CRXGate(0.2, ctrl_state=0)
    expected = {
        "base_gate",
        "_definition",
        "_name",
        "_num_qubits",
        "_num_clbits",
        "_params",
        "_label",
        "_num_ctrl_qubits",
        "_ctrl_state",
        "_open_ctrl",
    }
    assert set(vars(gate)) == expected
    assert gate.params is gate.base_gate.params and gate._params is not gate.params
    assert gate._params == [] and gate.params == [0.2]
    checks.append("controlled_parameters_delegate_to_actual_base_list")

    base = RXGate(0.3)
    left = ControlledGate("left", 2, [0.3], num_ctrl_qubits=1, base_gate=base)
    right = ControlledGate("right", 2, [0.3], num_ctrl_qubits=1, base_gate=base)
    # Constructor copying is separate from actual post-construction ownership.
    left.base_gate = right.base_gate = base
    base.params[0] = 0.6
    assert left.params is right.params is base.params and left.params == [0.6]
    assert left._params is not right._params
    checks.append("two_controlled_objects_can_share_one_base_and_parameter_list")

    for initial, final, initial_name, standard in ((0, 1, "crx_o0", False), (1, 0, "crx", True)):
        gate = CRXGate(0.2, ctrl_state=initial)
        circuit = QuantumCircuit(2)
        circuit.append(gate, [0, 1], copy=False)
        gate.ctrl_state = final
        gate.params[0] = 0.9
        item = circuit.data[0]
        assert item.operation is gate and item.name == initial_name
        assert item.is_standard_gate() is standard and item.params == [0.2]
        assert gate.name != initial_name and gate.params == [0.9]
        rebuilt = QuantumCircuit(2)
        rebuilt.append(gate, [0, 1], copy=False)
        assert rebuilt.data[0].is_standard_gate() is not standard
        assert rebuilt.data[0].name == gate.name and rebuilt.data[0].params == [0.9]
        assert gate._definition is None and gate.base_gate._definition is None
        checks.append("native_role_and_cache_survive_" + str(initial) + "_to_" + str(final))
        copied = item.copy()
        replaced = item.replace(qubits=item.qubits)
        for candidate in (copied, replaced):
            assert candidate.operation is gate and candidate.name == initial_name
            assert candidate.params == [0.2] and candidate.is_standard_gate() is standard
        checks.append("native_copy_preserves_retained_controlled_cache_" + str(initial))

    assert CXGate().to_mutable().base_gate is MCXGate(3).base_gate is XGate()
    checks.append("controlled_x_bases_share_sdk_singleton")

    definition = QuantumCircuit(2)
    definition.rx(0.2, 1)
    gate = CRXGate(0.2, ctrl_state=0)
    gate._definition = definition
    raw = vars(gate)
    assert raw["_definition"] is definition and gate._definition is definition
    assert raw["_name"] == "crx" and gate.name == "crx_o0"
    assert gate.base_gate._definition is None
    checks.append("raw_definition_and_raw_name_are_distinct_from_lazy_public_properties")

    print(
        json.dumps(
            {
                "scope": "trusted_controlled_ownership_audit",
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

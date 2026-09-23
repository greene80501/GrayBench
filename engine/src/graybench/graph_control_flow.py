"""Intrinsic branch values, distinct from retained Python control-flow objects."""

from graybench.circuit_wire import WireError, fields
from graybench.graph_circuit import CIRCUIT_CODECS, bit_state, restore_bit, validate_bit

REGISTER = CIRCUIT_CODECS["qiskit_register"]
BRANCH_FIELDS = {"qubits", "clbits", "qregs", "cregs", "phase", "operations"}


def encode_branch(circuit, ref, *, depth, budget):
    from graybench.graph_packed import encode_operations

    data = circuit._data
    if any(
        getattr(data, "num_" + name)
        for name in (
            "input_vars",
            "captured_vars",
            "declared_vars",
            "captured_stretches",
            "declared_stretches",
        )
    ):
        raise WireError("Branch variables require another graph codec")
    intrinsic = data.copy_empty_like()
    return {
        "qubits": [bit_state(b) for b in intrinsic.qubits],
        "clbits": [bit_state(b) for b in intrinsic.clbits],
        "qregs": [REGISTER.state(r, ref) for r in data.qregs],
        "cregs": [REGISTER.state(r, ref) for r in data.cregs],
        "phase": data.global_phase,
        "operations": encode_operations(data, intrinsic, ref, depth=depth, budget=budget),
    }


def validate_branch(state, index, *, depth, budget):
    from graybench.graph_circuit_data import CircuitDataCodec

    fields(state, BRANCH_FIELDS)
    CircuitDataCodec().validate_intrinsic(state, index, depth=depth, budget=budget)


def restore_branch(state, resolve):
    from qiskit import QuantumCircuit

    from graybench.graph_circuit_data import CircuitDataCodec
    from graybench.graph_packed import restore_operations

    data = CircuitDataCodec().allocate(state, {})
    restore_operations(data, state, resolve)
    data.global_phase = state["phase"]
    return QuantumCircuit._from_circuit_data(data, name="unnamed")


def encode_condition(condition):
    from qiskit.circuit import ClassicalRegister, Clbit

    if type(condition) is not tuple or len(condition) != 2:
        raise WireError("Classical expression condition requires another codec")
    target, value = condition
    if type(target) is Clbit:
        kind, state = "bit", bit_state(target)
    elif type(target) is ClassicalRegister:
        kind, state = "register", REGISTER.state(target, None)
    else:
        raise WireError("Unsupported native condition target")
    return {"kind": kind, "target": state, "value": value}


def validate_condition(state):
    fields(state, {"kind", "target", "value"})
    if state["kind"] == "bit":
        validate_bit(state["target"])
    elif state["kind"] == "register":
        REGISTER.validate(state["target"], {})
    else:
        raise WireError("Unknown native condition target")
    if state["target"]["family"] != "c" or type(state["value"]) not in (int, bool):
        raise WireError("Invalid native condition")
    if not 0 <= state["value"] < (1 << state["target"]["size"]):
        raise WireError("Native condition value exceeds register")


def restore_condition(state):
    target = (
        restore_bit(state["target"])
        if state["kind"] == "bit"
        else REGISTER.allocate(state["target"], {})
    )
    return target, state["value"]


def native_operation(item, intrinsic):
    return native_instruction(item, intrinsic).operation


def native_instruction(item, intrinsic):
    from qiskit import QuantumCircuit
    from qiskit.converters import circuit_to_dag, dag_to_circuit

    template = QuantumCircuit._from_circuit_data(intrinsic.copy_empty_like())
    template._data.append(item)
    # Clear native wrapper caches without copying retained Python leaf gates.
    # Default conversion copies those gates and breaks exported graph identity.
    native = dag_to_circuit(
        circuit_to_dag(template, copy_operations=False), copy_operations=False
    )._data[0]
    # Native conversion also discards cached singleton wrappers inside branches.
    # Restore the original intrinsic branch values without reinstating the outer
    # operation wrapper, including private anchor shells used during rehearsal.
    return native.replace(params=item.params)

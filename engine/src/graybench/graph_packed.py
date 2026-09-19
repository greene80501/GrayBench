"""Intrinsic packed standard gates; retained mutable Python operations are not flattened."""

from functools import cache

from graybench.circuit_wire import WireError, fields, integer
from graybench.graph_expressions import encode, replay, validate, vector_tokens


@cache
def standards():
    from qiskit.circuit.library import get_standard_gate_name_mapping

    return {
        name: (gate._standard_gate, gate.num_qubits, len(gate.params))
        for name, gate in get_standard_gate_name_mapping().items()
        if getattr(gate, "_standard_gate", None) is not None
    }


def encode_operations(data, intrinsic, ref):
    from qiskit.exceptions import QiskitError

    positions = {bit: i for i, bit in enumerate(intrinsic.qubits)}
    result = []
    if len(data) > 4096:
        raise WireError("Packed operation count exceeds limit")
    for i in range(len(data)):
        item = data[i]
        try:
            operation = item.operation
        except (TypeError, ValueError, QiskitError) as exc:
            raise WireError("Invalid packed operation parameters") from exc
        if not item.is_standard_gate() or item.name not in standards():
            raise WireError("Nonstandard instruction graph is not implemented")
        if operation.mutable and operation is data[i].operation:
            raise WireError("Retained Python operation requires its component graph")
        if operation.name != item.name or operation.num_qubits != len(item.qubits):
            raise WireError("Standard operation wrapper differs from intrinsic state")
        result.append(
            {
                "name": item.name,
                "qubits": [positions[q] for q in item.qubits],
                "params": [encode(p, ref) for p in item.params],
                "label": item.label,
            }
        )
    return result


def validate_operations(operations, qubits, index):
    if type(operations) is not list or len(operations) > 4096:
        raise WireError("Invalid packed operation stream")
    for op in operations:
        fields(op, {"name", "qubits", "params", "label"})
        name = op["name"]
        if type(name) is not str or name not in standards():
            raise WireError("Unknown fixed standard gate")
        _, width, count = standards()[name]
        if type(op["qubits"]) is not list or len(op["qubits"]) != width:
            raise WireError("Packed gate qubit count mismatch")
        for position in op["qubits"]:
            if integer(position, 511) >= qubits:
                raise WireError("Packed gate references missing intrinsic qubit")
        if type(op["params"]) is not list or len(op["params"]) != count:
            raise WireError("Packed gate parameter count mismatch")
        if op["label"] is not None and (type(op["label"]) is not str or len(op["label"]) > 4096):
            raise WireError("Invalid packed gate label")
        for parameter in op["params"]:
            validate(parameter, index)


def operation_tokens(operations):
    for op in operations:
        for parameter in op["params"]:
            yield from vector_tokens(parameter)


def restore_operations(target, state, resolve):
    from qiskit.circuit import CircuitInstruction
    from qiskit.exceptions import QiskitError

    # Use intrinsic membership, never a possibly divergent public cache list.
    qubits = target.copy_empty_like().qubits
    prepared = []
    try:
        for op in state["operations"]:
            prepared.append(
                CircuitInstruction.from_standard(
                    standards()[op["name"]][0],
                    [qubits[i] for i in op["qubits"]],
                    [replay(parameter, resolve) for parameter in op["params"]],
                    label=op["label"],
                )
            )
        target.clear()
        for item in prepared:
            target.append(item)
    except (TypeError, ValueError, QiskitError) as exc:
        raise WireError("Invalid packed operation reconstruction") from exc

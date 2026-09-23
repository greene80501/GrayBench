"""Intrinsic packed standard gates; retained mutable Python operations are not flattened."""

from functools import cache

from graybench.circuit_wire import WireError, WireLimitError, fields, integer
from graybench.graph_expressions import encode, replay, validate, vector_tokens
from graybench.graph_python_ops import (
    encode_python,
    python_tokens,
    restore_python,
    validate_intrinsic_matrix,
    validate_python,
)
from graybench.graph_symbolic import name_value
from graybench.scientific_wire import array_record, decode_array


@cache
def standards():
    from qiskit.circuit.library import get_standard_gate_name_mapping

    return {
        name: (gate._standard_gate, gate.num_qubits, len(gate.params))
        for name, gate in get_standard_gate_name_mapping().items()
        if getattr(gate, "_standard_gate", None) is not None
    }


def encode_operations(data, intrinsic, ref, *, depth=0, budget=None):
    from qiskit.exceptions import QiskitError

    from graybench.graph_singleton import SingletonCodec

    positions = {bit: i for i, bit in enumerate(intrinsic.qubits)}
    result = []
    if budget is None:
        budget = [4096]
    budget[0] -= len(data)
    if depth > 16 or budget[0] < 0:
        raise WireLimitError("Packed operation tree exceeds limit")
    for i in range(len(data)):
        item = data[i]
        try:
            operation = item.operation
        except (TypeError, ValueError, QiskitError) as exc:
            raise WireError("Invalid packed operation parameters") from exc
        singleton_ref = getattr(ref, "singleton_refs", False) and SingletonCodec().matches(
            operation
        )
        if (operation.mutable or singleton_ref) and operation is data[i].operation:
            result.append(
                encode_python(item, operation, intrinsic, ref, depth=depth, budget=budget)
            )
            continue
        from qiskit.circuit import Barrier, Delay, IfElseOp
        from qiskit.circuit.library import UnitaryGate
        from qiskit.dagcircuit import DAGOpNode

        if type(operation) is IfElseOp:
            result.append(
                encode_python(
                    item, operation, intrinsic, ref, depth=depth, budget=budget, retained=False
                )
            )
            continue
        if type(operation) in (Barrier, Delay, UnitaryGate):
            kind = {Barrier: "barrier", Delay: "delay", UnitaryGate: "unitary"}[type(operation)]
            if item.name != kind or item.clbits or (kind != "delay" and item.params):
                raise WireError("Unsupported packed native state")
            record = {
                "directive": kind,
                "num_qubits": DAGOpNode.from_instruction(item).num_qubits,
                "qubits": [positions[q] for q in item.qubits],
                "label": item.label,
            }
            if kind == "delay":
                record.update(unit=operation.unit, params=[encode(p, ref) for p in item.params])
            elif kind == "unitary":
                record.update(matrix=array_record(item.matrix), num_clbits=0, params=[])
            result.append(record)
            continue
        if not item.is_standard_gate() or item.name not in standards():
            raise WireError("Nonstandard instruction graph is not implemented")
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


def validate_operations(operations, qubits, clbits, index, *, depth=0, budget=None):
    if type(operations) is not list or len(operations) > 4096:
        raise WireError("Invalid packed operation stream")
    if budget is None:
        budget = [4096]
    budget[0] -= len(operations)
    if depth > 16 or budget[0] < 0:
        raise WireLimitError("Packed operation tree exceeds limit")
    for op in operations:
        if type(op) is dict and "directive" in op:
            kind = op["directive"]
            if type(kind) is not str or kind not in ("barrier", "delay", "unitary"):
                raise WireError("Unknown packed directive")
            extra = (
                {"unit", "params"}
                if kind == "delay"
                else ({"matrix", "num_clbits", "params"} if kind == "unitary" else set())
            )
            fields(op, {"directive", "num_qubits", "qubits", "label"} | extra)
            integer(op["num_qubits"], 512)
            if kind == "unitary":
                validate_intrinsic_matrix(op)
            if kind == "delay":
                name_value(op["unit"])
                if (
                    op["num_qubits"] != 1
                    or type(op["params"]) is not list
                    or len(op["params"]) != 1
                ):
                    raise WireError("Invalid native delay")
                validate(op["params"][0], index)
            if type(op["qubits"]) is not list or len(op["qubits"]) > 512:
                raise WireError("Invalid packed barrier operands")
            for position in op["qubits"]:
                if integer(position, 511) >= qubits:
                    raise WireError("Packed barrier references missing bit")
            if op["label"] is not None and (
                type(op["label"]) is not str or len(op["label"]) > 4096
            ):
                raise WireError("Invalid packed barrier label")
            continue
        if type(op) is dict and ("operation" in op or "control_flow" in op):
            validate_python(op, qubits, clbits, index, depth=depth, budget=budget)
            continue
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
        if "directive" in op:
            if op["directive"] == "delay":
                yield from vector_tokens(op["params"][0])
            continue
        if "operation" in op or "control_flow" in op:
            yield from python_tokens(op)
            continue
        for parameter in op["params"]:
            yield from vector_tokens(parameter)


def restore_operations(target, state, resolve):
    from qiskit.circuit import CircuitInstruction
    from qiskit.exceptions import QiskitError

    # Use intrinsic membership, never a possibly divergent public cache list.
    intrinsic = target.copy_empty_like()
    qubits, clbits = intrinsic.qubits, intrinsic.clbits
    prepared = []
    try:
        for op in state["operations"]:
            if "directive" in op:
                # Qiskit's Python constructor caches its Barrier object. A fixed
                # native conversion drops that cache, preserving the source's
                # fresh-wrapper behavior instead of inventing a retained object.
                from qiskit import QuantumCircuit
                from qiskit.converters import circuit_to_dag, dag_to_circuit

                template = QuantumCircuit(op["num_qubits"])
                if op["directive"] == "barrier":
                    template.barrier(label=op["label"])
                elif op["directive"] == "delay":
                    from qiskit.circuit import Delay

                    delay = Delay(replay(op["params"][0], resolve), op["unit"])
                    delay.label = op["label"]
                    template.append(delay, [0])
                else:
                    from qiskit.circuit.library import UnitaryGate

                    template.append(
                        UnitaryGate(
                            decode_array(op["matrix"]), label=op["label"], check_input=False
                        ),
                        template.qubits,
                    )
                native = dag_to_circuit(circuit_to_dag(template))._data[0]
                prepared.append(native.replace(qubits=[qubits[i] for i in op["qubits"]]))
                continue
            if "operation" in op or "control_flow" in op:
                item = restore_python(op, qubits, clbits, resolve)
                if "control_flow" in op:
                    from graybench.graph_control_flow import native_instruction

                    item = native_instruction(item, intrinsic)
                prepared.append(item)
                continue
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

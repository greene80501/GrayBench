"""Retained operations and the separate native instruction caches they accompany."""

from graybench.circuit_wire import WireError, fields, integer
from graybench.graph_expressions import encode, replay, validate, vector_tokens
from graybench.graph_scientific import node
from graybench.graph_symbolic import name_value
from graybench.scientific_wire import array_record, decode_array


def encode_python(item, operation, intrinsic, ref):
    from graybench.graph_instruction import InstructionCodec
    from graybench.graph_singleton import SingletonCodec

    if not (InstructionCodec().matches(operation) or SingletonCodec().matches(operation)):
        raise WireError("Retained Python operation requires another component codec")
    from qiskit.circuit import Parameter, ParameterExpression, ParameterVectorElement

    def parameter(value):
        if type(value) in (Parameter, ParameterExpression, ParameterVectorElement):
            return {"expression": encode(value, ref)}
        return {"value": ref(value)}

    qpos = {bit: i for i, bit in enumerate(intrinsic.qubits)}
    cpos = {bit: i for i, bit in enumerate(intrinsic.clbits)}
    from qiskit.dagcircuit import DAGOpNode

    native = DAGOpNode.from_instruction(item)
    result = {
        "native_standard": item.is_standard_gate(),
        "num_qubits": native.num_qubits,
        "num_clbits": native.num_clbits,
        "operation": ref(operation),
        "name": item.name,
        "qubits": [qpos[q] for q in item.qubits],
        "clbits": [cpos[c] for c in item.clbits],
        "params": [parameter(p) for p in item.params],
        "label": item.label,
    }
    from qiskit.circuit import Delay
    from qiskit.circuit.library import UnitaryGate

    if type(operation) is UnitaryGate:
        result["matrix"] = array_record(item.matrix)
    if type(operation) is Delay:
        # Read the intrinsic unit through a native conversion which discards the
        # Python operation cache. The retained wrapper may have been mutated.
        from qiskit import QuantumCircuit
        from qiskit.converters import circuit_to_dag, dag_to_circuit

        template = QuantumCircuit(len(item.qubits))
        template._data.append(item.replace(qubits=template.qubits))
        result["unit"] = dag_to_circuit(circuit_to_dag(template)).data[0].operation.unit
    return result


def validate_python(op, qubits, clbits, index):
    if type(op) is not dict:
        raise WireError("Invalid retained instruction record")
    component = node(op.get("operation"), index, {"python_instruction", "public_singleton"})
    is_delay = component["state"].get("class") == "delay"
    is_unitary = component["state"].get("class") == "unitary"
    fields(
        op,
        {
            "operation",
            "name",
            "qubits",
            "clbits",
            "params",
            "label",
            "num_qubits",
            "num_clbits",
            "native_standard",
        }
        | ({"unit"} if is_delay else set())
        | ({"matrix"} if is_unitary else set()),
    )
    if is_delay:
        name_value(op["unit"])
    if type(op["native_standard"]) is not bool:
        raise WireError("Invalid native standard-gate selector")
    integer(op["num_qubits"], 512)
    integer(op["num_clbits"], 512)
    if is_unitary:
        validate_intrinsic_matrix(op)
    node(op["operation"], index, {"python_instruction", "public_singleton"})
    name_value(op["name"])
    for key, count in (("qubits", qubits), ("clbits", clbits)):
        if type(op[key]) is not list or len(op[key]) > 512:
            raise WireError("Invalid retained instruction operands")
        for position in op[key]:
            if integer(position, 511) >= count:
                raise WireError("Retained instruction references missing bit")
    if type(op["params"]) is not list or len(op["params"]) > 4096:
        raise WireError("Invalid retained instruction parameter cache")
    for parameter in op["params"]:
        if type(parameter) is dict and set(parameter) == {"expression"}:
            validate(parameter["expression"], index)
        else:
            fields(parameter, {"value"})
    if op["label"] is not None:
        name_value(op["label"])


def python_tokens(op):
    yield op["operation"]
    for parameter in op["params"]:
        if "expression" in parameter:
            yield from vector_tokens(parameter["expression"])
        else:
            yield parameter["value"]


def validate_intrinsic_matrix(op):
    matrix = decode_array(op["matrix"])
    width = integer(op["num_qubits"], 7)
    if (
        op["matrix"]["kind"] != "ndarray_v1"
        or matrix.dtype.kind != "c"
        or matrix.dtype.itemsize != 16
        or matrix.shape != (1 << width, 1 << width)
        or op["num_clbits"] != 0
        or op["params"] != []
    ):
        raise WireError("Invalid intrinsic unitary matrix")


def intrinsic_matrix_bytes(operations):
    # Intrinsic matrices are values, not persistent Python graph objects.
    return sum(16 * (1 << (2 * op["num_qubits"])) for op in operations if "matrix" in op)


def restore_python(op, qubits, clbits, resolve):
    from qiskit.circuit import CircuitInstruction

    from graybench.graph_types import token_value

    operation = resolve(op["operation"]["ref"])
    actual = vars(operation)
    # The native instruction caches values when it first retains this object.
    # Recreate those caches while retaining the SAME Python operation, then put
    # its actual dictionary back. Only fixed exact classes reach this function.
    cached = dict(actual)
    cached.update(
        _name=op["name"],
        _num_qubits=op["num_qubits"],
        _num_clbits=op["num_clbits"],
        _params=[
            replay(p["expression"], resolve)
            if "expression" in p
            else token_value(p["value"], resolve)
            for p in op["params"]
        ],
        _label=op["label"],
    )
    if "unit" in op:
        cached["_unit"] = op["unit"]
    if "matrix" in op:
        cached["_params"] = [decode_array(op["matrix"])]
    replacements = [(operation, actual, cached)]
    if "base_gate" in actual:
        # Public controlled params delegate through the base chain. Cache replay
        # must temporarily supply the leaf list without replacing actual aliases.
        base = actual["base_gate"]
        seen = {id(operation)}
        while True:
            if id(base) in seen or len(seen) > 32:
                raise WireError("Invalid controlled cache base chain")
            seen.add(id(base))
            base_actual = vars(base)
            base_cached = dict(base_actual)
            base_cached["_params"] = cached["_params"]
            replacements.append((base, base_actual, base_cached))
            if "base_gate" not in base_actual:
                break
            base = base_actual["base_gate"]
        standard = getattr(type(operation), "_standard_gate", None)
        # Native Qiskit selects standard controlled operations only with closed
        # controls AND an unlabeled immediate base. Either field can have changed
        # since insertion. Supply a temporary extraction state for the declared
        # cached representation; restore the actual dictionaries in finally.
        cached["_open_ctrl"] = False
        if standard is not None:
            if op["native_standard"] and standard.name != op["name"]:
                raise WireError("Native standard class differs from retained operation")
            cached["_ctrl_state"] = (1 << standard.num_ctrl_qubits) - 1
            # The native Python branch reads the full cached name directly. A
            # temporary non-None base label selects it even for a closed gate.
            replacements[1][2]["_label"] = None if op["native_standard"] else ""
        elif op["native_standard"]:
            raise WireError("Native standard class differs from retained operation")
    applied = []
    try:
        for target, original, temporary in replacements:
            object.__setattr__(target, "__dict__", temporary)
            applied.append((target, original))
        return CircuitInstruction(
            operation, [qubits[i] for i in op["qubits"]], [clbits[i] for i in op["clbits"]]
        )
    finally:
        for target, original in reversed(applied):
            object.__setattr__(target, "__dict__", original)

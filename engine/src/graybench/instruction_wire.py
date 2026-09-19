"""Data-only instructions using fixed constructors and bounded nested circuit definitions."""

try:
    from .circuit_wire import (
        WireError,
        WireLimitError,
        decode_circuit,
        encode_circuit,
        fields,
        integer,
    )
    from .symbolic_wire import decode_parameter, encode_parameter
except ImportError:
    from circuit_wire import (
        WireError,
        WireLimitError,
        decode_circuit,
        encode_circuit,
        fields,
        integer,
    )
    from symbolic_wire import decode_parameter, encode_parameter


def encode_instruction(op, *, depth=0, operation_budget=None):
    from qiskit import QuantumCircuit
    from qiskit.circuit import Gate, Instruction
    from qiskit.circuit.library import LinearFunction

    if depth > 8:
        raise WireLimitError("Instruction definition nesting exceeds limit")
    if operation_budget is None:
        operation_budget = [1_000_000]
    if type(op) is LinearFunction:
        import numpy as np

        try:
            from .scientific_wire import MAX_BYTES, array_record
        except ImportError:
            from scientific_wire import MAX_BYTES, array_record
        if (
            len(op.params) != 2
            or type(op.linear) is not np.ndarray
            or op.linear.dtype != np.dtype(bool)
            or op.linear.shape != (op.num_qubits, op.num_qubits)
            or op.num_clbits != 0
        ):
            raise WireError("Unsupported LinearFunction matrix representation")
        if op.linear.nbytes > MAX_BYTES:
            raise WireLimitError("LinearFunction matrix exceeds codec capacity")
        return {
            "kind": "linear_function_v1",
            "name": op.name,
            "label": op.label,
            "linear": array_record(op.linear),
            "original": None
            if op.original_circuit is None
            else encode_circuit(
                op.original_circuit, depth=depth + 1, operation_budget=operation_budget
            ),
            "definition": None
            if op._definition is None
            else encode_circuit(op._definition, depth=depth + 1, operation_budget=operation_budget),
        }
    if type(op) in (Gate, Instruction):
        return {
            "kind": "generic_instruction_v1",
            "class": "Gate" if type(op) is Gate else "Instruction",
            "name": op.name,
            "qubits": op.num_qubits,
            "clbits": op.num_clbits,
            "label": op.label,
            "params": [encode_parameter(p) for p in op.params],
            "definition": None
            if op.definition is None
            else encode_circuit(op.definition, depth=depth + 1, operation_budget=operation_budget),
        }
    circuit = QuantumCircuit(op.num_qubits, op.num_clbits, name="__graybench_instruction__")
    circuit.append(op, range(op.num_qubits), range(op.num_clbits), copy=False)
    wire = encode_circuit(circuit, depth=depth + 1, operation_budget=operation_budget)
    if getattr(op, "_definition", None) is not None:
        template = decode_circuit(wire).data[0].operation.to_mutable()
        template._definition = None
        expected = template.definition
        if op._definition != expected or (
            expected is not None and op._definition.metadata != expected.metadata
        ):
            raise WireError("Customized standalone standard definitions require a faithful codec")
    return {
        "kind": "standard_instruction_v1",
        "mutable": op.mutable,
        "circuit": wire,
    }


def decode_instruction(value, *, depth=0, operation_budget=None):
    from qiskit.circuit import Gate, Instruction

    if depth > 8:
        raise WireLimitError("Instruction definition nesting exceeds limit")
    if type(value) is not dict:
        raise WireError("Expected an instruction record")
    if operation_budget is None:
        operation_budget = [1_000_000]
    if value.get("kind") == "linear_function_v1":
        import numpy as np
        from qiskit.circuit.library import LinearFunction

        try:
            from .scientific_wire import decode_array
        except ImportError:
            from scientific_wire import decode_array
        fields(value, {"kind", "name", "label", "linear", "original", "definition"})
        for key in ("name", "label"):
            if key == "label" and value[key] is None:
                continue
            if type(value[key]) is not str:
                raise WireError("Invalid LinearFunction name or label")
            if len(value[key]) > 4096:
                raise WireLimitError("LinearFunction name or label exceeds codec capacity")
        matrix = decode_array(value["linear"])
        if (
            type(matrix) is not np.ndarray
            or matrix.dtype != np.dtype(bool)
            or matrix.ndim != 2
            or matrix.shape[0] != matrix.shape[1]
        ):
            raise WireError("LinearFunction requires a square boolean matrix")
        op = LinearFunction(matrix, validate_input=False)
        op.name, op.label = value["name"], value["label"]
        if value["original"] is not None:
            op.params[1] = decode_circuit(
                value["original"], depth=depth + 1, operation_budget=operation_budget
            )
        if value["definition"] is not None:
            op.definition = decode_circuit(
                value["definition"], depth=depth + 1, operation_budget=operation_budget
            )
        return op
    if value.get("kind") == "standard_instruction_v1":
        fields(value, {"kind", "mutable", "circuit"})
        if type(value["mutable"]) is not bool:
            raise WireError("Invalid instruction mutability")
        circuit = decode_circuit(
            value["circuit"], depth=depth + 1, operation_budget=operation_budget
        )
        if len(circuit.data) != 1:
            raise WireError("Expected exactly one standalone instruction")
        op = circuit.data[0].operation
        if type(op) in (Gate, Instruction):
            raise WireError("Generic instruction in standard envelope")
        if value["mutable"] and not op.mutable:
            op = op.to_mutable()
        if op.mutable != value["mutable"]:
            raise WireError("Cannot represent instruction mutability")
        return op
    fields(value, {"kind", "class", "name", "qubits", "clbits", "label", "params", "definition"})
    if value["kind"] != "generic_instruction_v1" or value["class"] not in ("Gate", "Instruction"):
        raise WireError("Unknown instruction constructor")
    if type(value["name"]) is not str:
        raise WireError("Invalid instruction name")
    if len(value["name"]) > 4096:
        raise WireLimitError("Instruction name exceeds codec limit")
    if value["label"] is not None:
        if type(value["label"]) is not str:
            raise WireError("Invalid instruction label")
        if len(value["label"]) > 4096:
            raise WireLimitError("Instruction label exceeds codec limit")
    nq, nc = integer(value["qubits"]), integer(value["clbits"])
    if type(value["params"]) is not list:
        raise WireError("Invalid generic parameter list")
    if len(value["params"]) > 512:
        raise WireLimitError("Generic parameter count exceeds codec limit")
    context = {"parameters": {}, "vectors": {}}
    budget = [100000]
    params = [decode_parameter(p, context, budget=budget) for p in value["params"]]
    if value["class"] == "Gate":
        if nc:
            raise WireError("Gate cannot have classical bits")
        op = Gate(value["name"], nq, params, label=value["label"])
    else:
        op = Instruction(value["name"], nq, nc, params, label=value["label"])
    if value["definition"] is not None:
        definition = decode_circuit(
            value["definition"], depth=depth + 1, operation_budget=operation_budget
        )
        if definition.num_qubits != nq or definition.num_clbits != nc:
            raise WireError("Definition dimensions differ from instruction")
        op.definition = definition
    return op

"""Bounded data-only circuit exchange for explicitly supported instructions.

No QPY, pickle, Python expressions, dynamic imports, or candidate-selected constructors.
This codec is deliberately explicit about unsupported custom/control-flow operations.
Those interfaces require their own validated representation before a task can be admitted.
"""

import math


class WireError(ValueError):
    pass


def integer(value, maximum=512):
    if type(value) is not int or not 0 <= value <= maximum:
        raise WireError("Invalid bounded integer")
    return value


def number(value):
    if type(value) not in (int, float):
        raise WireError("Expected finite numeric parameter")
    try:
        if not math.isfinite(value):
            raise WireError("Expected finite numeric parameter")
    except OverflowError as exc:
        raise WireError("Numeric parameter exceeds representable range") from exc
    return value


def fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise WireError("Unexpected wire fields")


def indices(value, count):
    if type(value) is not list or len(value) > count:
        raise WireError("Invalid wire indices")
    if any(type(i) is not int or not 0 <= i < count for i in value):
        raise WireError("Wire index out of range")
    if len(set(value)) != len(value):
        raise WireError("Duplicate wire indices")
    return value


def encode_circuit(circuit):
    from qiskit.circuit.library import UnitaryGate, get_standard_gate_name_mapping

    try:
        from .scientific_wire import array_record
        from .symbolic_wire import encode_parameter
    except ImportError:
        from scientific_wire import array_record
        from symbolic_wire import encode_parameter

    standard = get_standard_gate_name_mapping()
    operations = []
    for item in circuit.data:
        op = item.operation
        if op.name == "barrier":
            params = []
        elif op.name == "unitary" and op.base_class is UnitaryGate:
            params = [array_record(op.params[0])]
        elif op.name in standard and op.base_class is standard[op.name].base_class:
            params = [encode_parameter(p) for p in op.params]
            if getattr(op, "ctrl_state", None) not in (
                None,
                2 ** getattr(op, "num_ctrl_qubits", 0) - 1,
            ):
                raise WireError("Open controls need an explicit codec")
        else:
            raise WireError("Unsupported instruction: " + op.name)
        operations.append(
            {
                "name": op.name,
                "params": params,
                "qubits": [circuit.find_bit(q).index for q in item.qubits],
                "clbits": [circuit.find_bit(c).index for c in item.clbits],
                "unit": op.unit if op.name == "delay" else None,
                "label": op.label,
            }
        )
    layout = None
    if circuit.layout is not None:
        layout = {
            "initial": circuit.layout.initial_index_layout(filter_ancillas=False),
            "routing": circuit.layout.routing_permutation(),
            "input_count": len(circuit.layout.final_index_layout()),
            "virtual_bits": bit_origins(
                sorted(
                    circuit.layout.input_qubit_mapping, key=circuit.layout.input_qubit_mapping.get
                )
            ),
        }
    return {
        "kind": "circuit_v4",
        "qubits": circuit.num_qubits,
        "clbits": circuit.num_clbits,
        "qubit_origins": bit_origins(circuit.qubits),
        "clbit_origins": bit_origins(circuit.clbits),
        "phase": encode_parameter(circuit.global_phase),
        "qregs": [[r.name, [circuit.find_bit(b).index for b in r]] for r in circuit.qregs],
        "cregs": [[r.name, [circuit.find_bit(b).index for b in r]] for r in circuit.cregs],
        "operations": operations,
        "layout": layout,
    }


def bit_origins(bits):
    return [
        None if bit._register is None else [bit._register.name, len(bit._register), bit._index]
        for bit in bits
    ]


def validate_origins(origins, count):
    if type(origins) is not list or len(origins) != count:
        raise WireError("Invalid bit-origin list")
    registers, seen = set(), set()
    for item in origins:
        if item is None:
            continue
        if type(item) is not list or len(item) != 3:
            raise WireError("Invalid bit origin")
        name, size, index = item
        if type(name) is not str or not 1 <= len(name) <= 256:
            raise WireError("Invalid backing register name")
        if not integer(size) or type(index) is not int or not 0 <= index < size:
            raise WireError("Invalid backing register position")
        if tuple(item) in seen:
            raise WireError("Duplicate registered bit origin")
        seen.add(tuple(item))
        registers.add((name, size))
    if sum(size for _, size in registers) > 8192:
        raise WireError("Backing-register allocation exceeds limit")


def build_bits(origins, bit_type, register_type):
    registers = {}
    bits = []
    for origin in origins:
        if origin is None:
            bits.append(bit_type())
        else:
            name, size, index = origin
            if (name, size) not in registers:
                registers[name, size] = register_type(size, name)
            bits.append(registers[name, size][index])
    return bits


def decode_circuit(value):
    try:
        from .symbolic_wire import decode_parameter
    except ImportError:
        from symbolic_wire import decode_parameter
    # Validate all sizes, tags, indices and numeric parameters before constructing anything.
    fields(
        value,
        {
            "kind",
            "qubits",
            "clbits",
            "phase",
            "qregs",
            "cregs",
            "operations",
            "layout",
            "qubit_origins",
            "clbit_origins",
        },
    )
    if value["kind"] != "circuit_v4":
        raise WireError("Unknown circuit codec")
    nq, nc = integer(value["qubits"]), integer(value["clbits"])
    context = {"parameters": {}, "vectors": {}}
    budget = [100000]
    phase = decode_parameter(value["phase"], context, budget=budget)
    validate_origins(value["qubit_origins"], nq)
    validate_origins(value["clbit_origins"], nc)
    for key, count in (("qregs", nq), ("cregs", nc)):
        regs = value[key]
        if type(regs) is not list or len(regs) > 512:
            raise WireError("Too many registers")
        names = set()
        for reg in regs:
            if type(reg) is not list or len(reg) != 2:
                raise WireError("Invalid register")
            name, bits = reg
            if type(name) is not str or not 1 <= len(name) <= 256 or name in names:
                raise WireError("Invalid or duplicate register name")
            names.add(name)
            indices(bits, count)
    ops = value["operations"]
    if type(ops) is not list or len(ops) > 20_000:
        raise WireError("Instruction count exceeds codec limit")
    from qiskit.circuit.library import UnitaryGate, get_standard_gate_name_mapping

    try:
        from .scientific_wire import decode_array
    except ImportError:
        from scientific_wire import decode_array

    standard = get_standard_gate_name_mapping()
    decoded_params = []
    matrix_bytes = 0
    for op in ops:
        fields(op, {"name", "params", "qubits", "clbits", "unit", "label"})
        if op["label"] is not None and (type(op["label"]) is not str or len(op["label"]) > 4096):
            raise WireError("Invalid instruction label")
        if type(op["name"]) is not str or op["name"] not in {*standard, "barrier", "unitary"}:
            raise WireError("Instruction is not in the fixed constructor registry")
        if type(op["params"]) is not list or len(op["params"]) > 8:
            raise WireError("Invalid parameter list")
        indices(op["qubits"], nq)
        indices(op["clbits"], nc)
        if op["name"] == "unitary":
            if len(op["params"]) != 1 or op["clbits"] or not 1 <= len(op["qubits"]) <= 7:
                raise WireError("Invalid matrix instruction arity")
            matrix = decode_array(op["params"][0])
            size = 2 ** len(op["qubits"])
            if matrix.shape != (size, size) or matrix.dtype.kind != "c":
                raise WireError("Invalid matrix instruction shape or dtype")
            matrix_bytes += matrix.nbytes
            if matrix_bytes > 512 * 1024:
                raise WireError("Total matrix storage exceeds limit")
            decoded_params.append([matrix])
        else:
            decoded_params.append(
                [decode_parameter(p, context, budget=budget) for p in op["params"]]
            )
        if op["name"] == "barrier":
            if op["params"] or op["clbits"]:
                raise WireError("Invalid barrier")
        elif op["name"] != "unitary":
            template = standard[op["name"]]
            if (
                len(op["qubits"]) != template.num_qubits
                or len(op["clbits"]) != template.num_clbits
                or len(op["params"]) != len(template.params)
            ):
                raise WireError("Instruction arity mismatch")
        if op["name"] == "delay":
            if op["unit"] not in {"dt", "s", "ms", "us", "ns", "ps"}:
                raise WireError("Invalid delay unit")
        elif op["unit"] is not None:
            raise WireError("Unexpected instruction unit")
    layout = value["layout"]
    if layout is not None:
        fields(layout, {"initial", "routing", "input_count", "virtual_bits"})
        validate_origins(layout["virtual_bits"], nq)
        for key in ("initial", "routing"):
            if len(indices(layout[key], nq)) != nq:
                raise WireError("Layout must be a complete permutation")
        integer(layout["input_count"], nq)

    from qiskit import QuantumCircuit
    from qiskit.circuit import Barrier, ClassicalRegister, Clbit, QuantumRegister, Qubit
    from qiskit.transpiler import Layout, TranspileLayout

    qubits = build_bits(value["qubit_origins"], Qubit, QuantumRegister)
    clbits = build_bits(value["clbit_origins"], Clbit, ClassicalRegister)
    circuit = QuantumCircuit(qubits, clbits)
    for name, bits in value["qregs"]:
        circuit.add_register(QuantumRegister(name=name, bits=[qubits[i] for i in bits]))
    for name, bits in value["cregs"]:
        circuit.add_register(ClassicalRegister(name=name, bits=[clbits[i] for i in bits]))
    circuit.global_phase = phase
    for op, params in zip(ops, decoded_params, strict=True):
        if op["name"] == "barrier":
            instruction = Barrier(len(op["qubits"]))
        elif op["name"] == "delay":
            instruction = standard["delay"].base_class(*params, unit=op["unit"])
        elif op["name"] == "unitary":
            # Preserve submitted values, including nonunitary matrices constructed with checks
            # disabled. Shape/allocation are validated above; correctness belongs to the judge.
            instruction = UnitaryGate(params[0], check_input=False, num_qubits=len(op["qubits"]))
        else:
            instruction = standard[op["name"]].base_class(*params)
        if op["label"] is not None:
            instruction = instruction.to_mutable()
            instruction.label = op["label"]
        circuit.append(instruction, op["qubits"], op["clbits"])
    if layout is not None:
        virtual = build_bits(layout["virtual_bits"], Qubit, QuantumRegister)
        circuit._layout = TranspileLayout(
            Layout({virtual[i]: p for i, p in enumerate(layout["initial"])}),
            {bit: i for i, bit in enumerate(virtual)},
            Layout({qubits[i]: p for i, p in enumerate(layout["routing"])}),
            _input_qubit_count=layout["input_count"],
            _output_qubit_list=qubits,
        )
    return circuit

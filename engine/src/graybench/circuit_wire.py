"""Bounded data-only circuit exchange for explicitly supported instructions.

No QPY, pickle, Python expressions, dynamic imports, or candidate-selected constructors.
This codec is deliberately explicit about unsupported custom/control-flow operations.
Those interfaces require their own validated representation before a task can be admitted.
"""

import base64
import json
import math
import zlib

MAX_CIRCUIT_BYTES = 64 * 1024 * 1024
MAX_COMPRESSED_BYTES = 512 * 1024


def pack_circuit(value):
    """Compress data only; preserve every instruction, label and parameter exactly."""
    raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    if len(raw) < 32768:
        return value
    if len(raw) > MAX_CIRCUIT_BYTES:
        raise WireLimitError("Circuit representation exceeds decoded byte limit")
    compressed = zlib.compress(raw)
    if len(compressed) > MAX_COMPRESSED_BYTES:
        raise WireLimitError("Circuit representation exceeds compressed byte limit")
    return {
        "kind": "compressed_circuit_v1",
        "bytes": base64.b64encode(compressed).decode(),
        "size": len(raw),
    }


def unpack_circuit(value):
    fields(value, {"kind", "bytes", "size"})
    if value["kind"] != "compressed_circuit_v1":
        raise WireError("Unknown compressed circuit format")
    size = integer(value["size"], MAX_CIRCUIT_BYTES)
    encoded = value["bytes"]
    if type(encoded) is not str:
        raise WireError("Invalid compressed circuit encoding")
    if len(encoded) > 4 * ((MAX_COMPRESSED_BYTES + 2) // 3):
        raise WireLimitError("Compressed circuit exceeds byte limit")
    try:
        compressed = base64.b64decode(encoded, validate=True)
        if len(compressed) > MAX_COMPRESSED_BYTES:
            raise WireLimitError("Compressed circuit exceeds byte limit")
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, size + 1)
        if len(raw) != size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise WireError("Invalid or oversized compressed circuit stream")
        result = json.loads(raw)
    except WireLimitError:
        raise
    except (ValueError, zlib.error, RecursionError) as exc:
        raise WireError("Invalid compressed circuit") from exc
    return decode_circuit(result)


class WireError(ValueError):
    pass


class WireLimitError(WireError):
    """A representation exceeds this codec; no correctness conclusion follows."""


def integer(value, maximum=512):
    if type(value) is not int or value < 0:
        raise WireError("Invalid bounded integer")
    if value > maximum:
        raise WireLimitError("Integer exceeds codec allocation limit")
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


def encode_circuit(circuit, *, depth=0, operation_budget=None):
    if depth > 8:
        raise WireLimitError("Instruction definition nesting exceeds limit")
    if operation_budget is None:
        operation_budget = [1_000_000]
    operation_budget[0] -= len(circuit.data)
    if operation_budget[0] < 0:
        raise WireLimitError("Instruction graph exceeds codec limit")
    from qiskit.circuit import Gate, Instruction
    from qiskit.circuit.library import (
        LinearFunction,
        StatePreparation,
        UnitaryGate,
        get_standard_gate_name_mapping,
    )

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
        wire_name = op.name
        if type(op) in (Gate, Instruction, LinearFunction):
            try:
                from .instruction_wire import encode_instruction
            except ImportError:
                from instruction_wire import encode_instruction
            wire_name = "__generic_definition_v1__"
            params = [encode_instruction(op, depth=depth + 1, operation_budget=operation_budget)]
        elif op.name == "barrier":
            params = []
        elif op.base_class is StatePreparation:
            try:
                from .preparation_wire import encode_preparation
            except ImportError:
                from preparation_wire import encode_preparation
            params = [encode_preparation(op)]
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
                "name": wire_name,
                "params": params,
                "qubits": [circuit.find_bit(q).index for q in item.qubits],
                "clbits": [circuit.find_bit(c).index for c in item.clbits],
                "unit": op.unit if wire_name == "delay" else None,
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
        "kind": "circuit_v5",
        "name": circuit.name,
        "metadata": json_metadata(circuit.metadata),
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
        raise WireLimitError("Backing-register allocation exceeds limit")


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


def decode_circuit(value, *, depth=0, operation_budget=None):
    if depth > 8:
        raise WireLimitError("Instruction definition nesting exceeds limit")
    if operation_budget is None:
        operation_budget = [1_000_000]
    try:
        from .symbolic_wire import decode_parameter
    except ImportError:
        from symbolic_wire import decode_parameter
    # Validate all sizes, tags, indices and numeric parameters before constructing anything.
    fields(
        value,
        {
            "kind",
            "name",
            "metadata",
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
    if value["kind"] != "circuit_v5":
        raise WireError("Unknown circuit codec")
    if type(value["name"]) is not str:
        raise WireError("Invalid circuit name")
    if len(value["name"]) > 4096:
        raise WireLimitError("Circuit name exceeds codec limit")
    metadata = json_metadata(value["metadata"])
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
    if type(ops) is not list:
        raise WireError("Expected instruction list")
    if len(ops) > 1_000_000:
        raise WireLimitError("Instruction count exceeds codec limit")
    operation_budget[0] -= len(ops)
    if operation_budget[0] < 0:
        raise WireLimitError("Instruction graph exceeds codec limit")
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
        if op["label"] is not None:
            if type(op["label"]) is not str:
                raise WireError("Invalid instruction label")
            if len(op["label"]) > 4096:
                raise WireLimitError("Instruction label exceeds codec limit")
        if type(op["name"]) is not str or op["name"] not in {
            *standard,
            "barrier",
            "unitary",
            "state_preparation",
            "state_preparation_dg",
            "__generic_definition_v1__",
        }:
            raise WireError("Instruction is not in the fixed constructor registry")
        if type(op["params"]) is not list or len(op["params"]) > 8:
            raise WireError("Invalid parameter list")
        indices(op["qubits"], nq)
        indices(op["clbits"], nc)
        if op["name"] == "__generic_definition_v1__":
            if len(op["params"]) != 1:
                raise WireError("Invalid generic instruction envelope")
            try:
                from .instruction_wire import decode_instruction
            except ImportError:
                from instruction_wire import decode_instruction
            instruction = decode_instruction(
                op["params"][0], depth=depth + 1, operation_budget=operation_budget
            )
            if instruction.num_qubits != len(op["qubits"]) or instruction.num_clbits != len(
                op["clbits"]
            ):
                raise WireError("Generic instruction arity mismatch")
            decoded_params.append([instruction])
        elif op["name"] in ("state_preparation", "state_preparation_dg"):
            if len(op["params"]) != 1 or op["clbits"]:
                raise WireError("Invalid preparation arity")
            try:
                from .preparation_wire import decode_preparation
            except ImportError:
                from preparation_wire import decode_preparation
            decoded_params.append(
                [decode_preparation(op["params"][0], len(op["qubits"]), op["name"])]
            )
        elif op["name"] == "unitary":
            if len(op["params"]) != 1 or op["clbits"] or not 1 <= len(op["qubits"]) <= 7:
                raise WireError("Invalid matrix instruction arity")
            matrix = decode_array(op["params"][0])
            size = 2 ** len(op["qubits"])
            if matrix.shape != (size, size) or matrix.dtype.kind != "c":
                raise WireError("Invalid matrix instruction shape or dtype")
            matrix_bytes += matrix.nbytes
            if matrix_bytes > 512 * 1024:
                raise WireLimitError("Total matrix storage exceeds limit")
            decoded_params.append([matrix])
        else:
            decoded_params.append(
                [decode_parameter(p, context, budget=budget) for p in op["params"]]
            )
        if op["name"] == "barrier":
            if op["params"] or op["clbits"]:
                raise WireError("Invalid barrier")
        elif op["name"] not in (
            "unitary",
            "state_preparation",
            "state_preparation_dg",
            "__generic_definition_v1__",
        ):
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
        if type(layout["input_count"]) is not int or not 0 <= layout["input_count"] <= nq:
            raise WireError("Layout input count exceeds circuit dimensions")

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
    circuit.name = value["name"]
    circuit.metadata = metadata
    circuit.global_phase = phase
    for op, params in zip(ops, decoded_params, strict=True):
        if op["name"] == "__generic_definition_v1__":
            instruction = params[0]
        elif op["name"] == "barrier":
            instruction = Barrier(len(op["qubits"]))
        elif op["name"] == "delay":
            instruction = standard["delay"].base_class(*params, unit=op["unit"])
        elif op["name"] in ("state_preparation", "state_preparation_dg"):
            instruction = params[0]
            instruction.label = op["label"]
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


def json_metadata(value):
    """Preserve JSON metadata types exactly, refusing coercion of keys/tuples/objects."""
    budget = [10000]

    def visit(item, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 16:
            raise WireLimitError("Circuit metadata exceeds structural limit")
        if item is None or type(item) in (bool, str, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                visit(child, depth + 1)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                visit(child, depth + 1)
            return
        raise WireError("Unsupported circuit metadata type")

    if value is not None and type(value) is not dict:
        raise WireError("Expected a metadata dictionary")
    visit(value)
    raw = json.dumps(value, allow_nan=False).encode()
    if len(raw) > 65536:
        raise WireLimitError("Circuit metadata exceeds byte limit")
    return json.loads(raw)

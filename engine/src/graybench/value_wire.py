"""Shared bounded value codec used on both sides of the candidate boundary."""

import math

try:  # Worker files are copied without installing the host orchestration package.
    from .circuit_wire import (
        WireError,
        WireLimitError,
        decode_circuit,
        encode_circuit,
        pack_circuit,
        unpack_circuit,
    )
except ImportError:
    from circuit_wire import (
        WireError,
        WireLimitError,
        decode_circuit,
        encode_circuit,
        pack_circuit,
        unpack_circuit,
    )

try:
    from .scientific_wire import decode_scientific, encode_scientific
except ImportError:
    from scientific_wire import decode_scientific, encode_scientific


def encode(item, depth=0):
    if depth > 32:
        raise WireLimitError("Result nesting exceeds wire limit")
    if item is None or type(item) in (bool, str, int):
        return item
    if type(item) is float and math.isfinite(item):
        return item
    if type(item) is complex:
        if not math.isfinite(item.real) or not math.isfinite(item.imag):
            raise WireError("Non-finite Python complex scalar")
        return {"kind": "complex_v1", "real": item.real, "imag": item.imag}
    if type(item) in (list, tuple):
        return {"kind": type(item).__name__, "items": [encode(x, depth + 1) for x in item]}
    if type(item) is dict:
        return {
            "kind": "dict",
            "items": [[encode(k, depth + 1), encode(v, depth + 1)] for k, v in item.items()],
        }
    from qiskit import QuantumCircuit
    from qiskit.circuit import ParameterExpression
    from qiskit.transpiler import PropertySet

    if type(item) is PropertySet:
        if vars(item):
            raise WireError("PropertySet has unsupported instance attributes")
        return {
            "kind": "property_set_v1",
            "items": [[encode(k, depth + 1), encode(v, depth + 1)] for k, v in item.items()],
        }

    if isinstance(item, ParameterExpression):
        try:
            from .symbolic_wire import encode_parameter
        except ImportError:
            from symbolic_wire import encode_parameter
        return encode_parameter(item)

    if isinstance(item, QuantumCircuit):
        return pack_circuit(encode_circuit(item))
    from qiskit.circuit import Instruction

    if isinstance(item, Instruction):
        try:
            from .instruction_wire import encode_instruction
        except ImportError:
            from instruction_wire import encode_instruction
        return encode_instruction(item)
    scientific = encode_scientific(item)
    if scientific is not None:
        return scientific
    try:
        from .primitive_wire import encode_primitive
    except ImportError:
        from primitive_wire import encode_primitive
    primitive = encode_primitive(item, depth)
    if primitive is not None:
        return primitive
    raise WireError("Unsupported wire value: " + type(item).__name__)


def decode(value, depth=0, budget=None):
    if budget is None:
        budget = [100_000]
    budget[0] -= 1
    if depth > 32 or budget[0] < 0:
        raise WireLimitError("Result exceeds structural limit")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is dict and value.get("kind") == "cnot_dihedral_v1":
        try:
            from .scientific_wire import decode_dihedral
        except ImportError:
            from scientific_wire import decode_dihedral
        return decode_dihedral(value)
    if type(value) is dict and value.get("kind") == "complex_v1":
        if set(value) != {"kind", "real", "imag"} or any(
            type(value[k]) is not float or not math.isfinite(value[k]) for k in ("real", "imag")
        ):
            raise WireError("Invalid complex scalar")
        return complex(value["real"], value["imag"])
    if type(value) is dict and value.get("kind") in {
        "bit_array_v1",
        "data_bin_v1",
        "primitive_result_v1",
        "pub_result_v1",
        "sampler_pub_result_v1",
    }:
        try:
            from .primitive_wire import decode_primitive
        except ImportError:
            from primitive_wire import decode_primitive
        return decode_primitive(value, depth, budget)
    if type(value) is dict and value.get("kind") in {
        "ndarray_v1",
        "numpy_scalar_v1",
        "statevector_v1",
        "densitymatrix_v1",
        "operator_v1",
        "scalar_op_v1",
        "sparse_pauli_op_v1",
        "choi_v1",
        "clifford_v1",
        "stabilizer_v1",
    }:
        return decode_scientific(value)
    if type(value) is dict and value.get("kind") in {
        "parameter_v1",
        "vector_element_v1",
        "expression_v1",
    }:
        try:
            from .symbolic_wire import decode_parameter
        except ImportError:
            from symbolic_wire import decode_parameter
        return decode_parameter(value)
    if type(value) is dict and value.get("kind") in (
        "generic_instruction_v1",
        "standard_instruction_v1",
        "linear_function_v1",
        "numeric_gate_v1",
        "controlled_gate_v1",
    ):
        try:
            from .instruction_wire import decode_instruction
        except ImportError:
            from instruction_wire import decode_instruction
        return decode_instruction(value)
    if type(value) is dict and value.get("kind") == "circuit_v5":
        return decode_circuit(value)
    if type(value) is dict and value.get("kind") == "compressed_circuit_v1":
        return unpack_circuit(value)
    if type(value) is not dict or set(value) != {"kind", "items"}:
        raise WireError("Invalid result wire type")
    if type(value["items"]) is not list:
        raise WireError("Invalid result items")
    if value["kind"] in ("list", "tuple"):
        items = [decode(x, depth + 1, budget) for x in value["items"]]
        return items if value["kind"] == "list" else tuple(items)
    if value["kind"] in ("dict", "property_set_v1"):
        result = {}
        for pair in value["items"]:
            if type(pair) is not list or len(pair) != 2:
                raise WireError("Invalid dictionary pair")
            key = decode(pair[0], depth + 1, budget)
            try:
                if key in result:
                    raise WireError("Duplicate dictionary key")
                result[key] = decode(pair[1], depth + 1, budget)
            except TypeError as exc:
                raise WireError("Unhashable dictionary key") from exc
        if value["kind"] == "property_set_v1":
            from qiskit.transpiler import PropertySet

            return PropertySet(result)
        return result
    raise WireError("Unknown result kind")

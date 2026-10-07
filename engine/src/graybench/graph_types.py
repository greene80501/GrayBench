"""Closed container registry for the experimental reference-graph protocol."""

import math
from dataclasses import dataclass

from graybench.circuit_wire import WireError
from graybench.graph_circuit import CIRCUIT_CODECS
from graybench.graph_circuit_data import CIRCUIT_DATA_CODECS
from graybench.graph_classical import ClassicalExpressionCodec
from graybench.graph_expressions import ExpressionCodec
from graybench.graph_instruction import InstructionCodec
from graybench.graph_loops import RangeCodec
from graybench.graph_native import NATIVE_CODECS
from graybench.graph_numeric import ARRAY_CODECS
from graybench.graph_object_arrays import OBJECT_ARRAY_CODECS
from graybench.graph_primitive import PRIMITIVE_CODECS
from graybench.graph_quantum_circuit import QUANTUM_CIRCUIT_CODECS
from graybench.graph_scientific import SCIENTIFIC_CODECS
from graybench.graph_singleton import SingletonCodec
from graybench.graph_symbolic import SYMBOL_CODECS

SCALAR_MISSING = object()


def scalar_record(value):
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is complex and math.isfinite(value.real) and math.isfinite(value.imag):
        return {"kind": "complex_v1", "real": value.real, "imag": value.imag}
    return SCALAR_MISSING


def scalar_value(value):
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is dict and set(value) == {"kind", "real", "imag"}:
        if value["kind"] == "complex_v1" and all(
            type(value[k]) is float and math.isfinite(value[k]) for k in ("real", "imag")
        ):
            return complex(value["real"], value["imag"])
    raise WireError("Invalid graph scalar")


def token_value(token, resolve):
    if type(token) is dict and set(token) == {"ref"}:
        return resolve(token["ref"])
    return scalar_value(token)


@dataclass(frozen=True)
class ContainerCodec:
    kind: str

    @property
    def immutable(self):
        return self.kind == "tuple"

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()

    def validate_update(self, previous, state):
        pass  # Tuple immutability is checked on canonical wire bytes in the arena.

    def prepare(self, state, resolve, shape_index):
        return self.populate(self.allocate(state, shape_index), state, resolve)

    def matches(self, value):
        if self.kind == "qiskit_frozen_list":
            from qiskit.circuit.singleton import _frozenlist

            return type(value) is _frozenlist
        if self.kind in ("list", "tuple", "dict"):
            return type(value) is {"list": list, "tuple": tuple, "dict": dict}[self.kind]
        from qiskit.transpiler import PropertySet

        return type(value) is PropertySet

    def state(self, value, ref):
        if self.kind == "property_set" and vars(value):
            raise WireError("PropertySet instance attributes require a graph codec")
        if self.kind in ("list", "tuple", "qiskit_frozen_list"):
            return [ref(item) for item in value]
        return [[ref(key), ref(item)] for key, item in value.items()]

    def validate(self, state, shape_index):
        if type(state) is not list:
            raise WireError("Invalid graph container state")
        if self.kind in ("dict", "property_set") and any(
            type(pair) is not list or len(pair) != 2 for pair in state
        ):
            raise WireError("Invalid graph mapping entry")

    def tokens(self, state):
        if self.kind in ("list", "tuple", "qiskit_frozen_list"):
            yield from state
        else:
            for pair in state:
                yield from pair

    def allocate(self, state, shape_index):
        if self.kind == "qiskit_frozen_list":
            from qiskit.circuit.singleton import _frozenlist

            return _frozenlist()
        if self.kind == "list":
            return []
        if self.kind == "tuple":
            return None  # Construct after mutable shells exist.
        if self.kind == "dict":
            return {}
        from qiskit.transpiler import PropertySet

        return PropertySet()

    def populate(self, target, state, resolve):
        values = [token_value(token, resolve) for token in self.tokens(state)]
        if self.kind == "tuple":
            return tuple(values)
        if self.kind in ("list", "qiskit_frozen_list"):
            list.__setitem__(target, slice(None), values)
            return target
        proposed = {}
        for index in range(0, len(values), 2):
            key, item = values[index : index + 2]
            try:
                if key in proposed:
                    raise WireError("Duplicate graph dictionary key")
                proposed[key] = item
            except (TypeError, RecursionError) as exc:
                raise WireError("Invalid graph dictionary key") from exc
        dict.clear(target)
        dict.update(target, proposed)
        return target

    def apply(self, target, prepared):
        if self.kind in ("list", "qiskit_frozen_list"):
            list.__setitem__(target, slice(None), prepared)
        elif self.kind in ("dict", "property_set"):
            dict.clear(target)
            dict.update(target, prepared)
        else:
            raise WireError("Immutable graph node cannot be updated")


REGISTRY = {
    name: ContainerCodec(name)
    for name in ("list", "tuple", "dict", "property_set", "qiskit_frozen_list")
}
REGISTRY.update(NATIVE_CODECS)
REGISTRY.update(ARRAY_CODECS)
REGISTRY.update(OBJECT_ARRAY_CODECS)
REGISTRY.update(SCIENTIFIC_CODECS)
REGISTRY.update(PRIMITIVE_CODECS)
REGISTRY.update(SYMBOL_CODECS)
REGISTRY.update(CIRCUIT_CODECS)
REGISTRY.update(CIRCUIT_DATA_CODECS)
REGISTRY.update(QUANTUM_CIRCUIT_CODECS)
REGISTRY["parameter_expression"] = ExpressionCodec()
REGISTRY["classical_expression"] = ClassicalExpressionCodec()
REGISTRY["range"] = RangeCodec()
REGISTRY["python_instruction"] = InstructionCodec()
REGISTRY["public_singleton"] = SingletonCodec()


def codec_for(value):
    for codec in REGISTRY.values():
        if codec.matches(value):
            return codec
    raise WireError("Unsupported graph object: " + type(value).__name__)

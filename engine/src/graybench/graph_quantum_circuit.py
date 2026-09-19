"""Fixed Python circuit components; native instruction storage is a separate node."""

from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError, fields
from graybench.graph_scientific import node, validate_attributes
from graybench.graph_symbolic import name_value

QC_FIELDS = (
    "_base_name",
    "name",
    "_builder_api",
    "_op_start_times",
    "_control_flow_scopes",
    "_data",
    "_ancillas",
    "_layout",
    "_duration",
    "_unit",
    "_metadata",
)
ATTRS = {
    "quantum_circuit": tuple((key, key) for key in QC_FIELDS),
    "circuit_data_view": (("_circuit", "_circuit"),),
}


@cache
def classes():
    from qiskit import QuantumCircuit
    from qiskit.circuit.quantumcircuit import _OuterCircuitScopeInterface
    from qiskit.circuit.quantumcircuitdata import QuantumCircuitData

    return {
        "quantum_circuit": QuantumCircuit,
        "circuit_scope": _OuterCircuitScopeInterface,
        "circuit_data_view": QuantumCircuitData,
    }


@dataclass(frozen=True)
class CircuitComponentCodec:
    kind: str
    immutable: bool = False

    def matches(self, value):
        return type(value) is classes()[self.kind]

    def state(self, value, ref):
        if self.kind == "circuit_scope":
            return {"circuit": ref(value.circuit)}
        expected = {key for key, _ in ATTRS[self.kind]}
        if set(vars(value)) != expected:
            raise WireError("Extra or missing circuit instance fields are unsupported")
        return {
            **{key: ref(vars(value)[attr]) for key, attr in ATTRS[self.kind]},
            "attributes": ref(vars(value)),
        }

    def validate(self, state, index):
        if self.kind == "circuit_scope":
            fields(state, {"circuit"})
            node(state["circuit"], index, {"quantum_circuit"})
            return
        fields(state, {key for key, _ in ATTRS[self.kind]} | {"attributes"})
        validate_attributes(state, index, ATTRS[self.kind])
        if self.kind == "circuit_data_view":
            node(state["_circuit"], index, {"quantum_circuit"})
            return
        for key in ("_base_name", "name", "_unit"):
            name_value(state[key])
        node(state["_data"], index, {"circuit_data"})
        node(state["_builder_api"], index, {"circuit_scope"})
        node(state["_metadata"], index, {"dict"})
        scopes = node(state["_control_flow_scopes"], index, {"list"})["state"]
        if scopes != []:
            raise WireError("Active circuit builder scopes require another codec")
        node(state["_ancillas"], index, {"list"})
        if state["_layout"] is not None:
            raise WireError("Circuit layout graph is not implemented")
        if state["_op_start_times"] is not None:
            node(state["_op_start_times"], index, {"list"})
        duration = state["_duration"]
        if duration is not None and type(duration) not in (float, int):
            raise WireError("Unsupported circuit duration component")

    def tokens(self, state):
        if self.kind == "circuit_scope":
            return (state["circuit"],)
        return tuple(state[key] for key, _ in ATTRS[self.kind]) + (state["attributes"],)

    def allocate(self, state, index):
        return object.__new__(classes()[self.kind])

    def prepare(self, state, resolve, index):
        return resolve(
            state["circuit"]["ref"] if self.kind == "circuit_scope" else state["attributes"]["ref"]
        )

    def apply(self, target, prepared):
        if self.kind == "circuit_scope":
            object.__setattr__(target, "circuit", prepared)
        else:
            object.__setattr__(target, "__dict__", prepared)

    def validate_update(self, previous, state):
        pass

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()


QUANTUM_CIRCUIT_CODECS = {
    kind: CircuitComponentCodec(kind)
    for kind in ("quantum_circuit", "circuit_scope", "circuit_data_view")
}

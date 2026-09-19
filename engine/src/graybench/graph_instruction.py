"""Fixed mutable Python instruction components, including raw definition references."""

from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError, fields, integer
from graybench.graph_scientific import node, validate_attributes
from graybench.graph_symbolic import name_value

ATTRS = tuple(
    (key, key)
    for key in ("_name", "_num_qubits", "_num_clbits", "_params", "_label", "_definition")
)


@cache
def classes():
    from qiskit.circuit import Gate, Instruction
    from qiskit.circuit.library import get_standard_gate_name_mapping

    result = {"gate": Gate, "instruction": Instruction}
    expected = {key for key, _ in ATTRS}
    for name, template in get_standard_gate_name_mapping().items():
        if set(vars(template)) == expected:
            result["standard:" + name] = template.base_class
    return result


@dataclass(frozen=True)
class InstructionCodec:
    kind: str = "python_instruction"
    immutable: bool = False

    def matches(self, value):
        return type(value) in classes().values()

    def state(self, value, ref):
        if set(vars(value)) != {key for key, _ in ATTRS}:
            raise WireError("Extra or missing instruction fields require another codec")
        selector = next(key for key, cls in classes().items() if type(value) is cls)
        return {
            "class": selector,
            "attributes": ref(vars(value)),
            **{key: ref(vars(value)[key]) for key, _ in ATTRS},
        }

    def validate(self, state, index):
        fields(state, {"class", "attributes"} | {key for key, _ in ATTRS})
        if type(state["class"]) is not str or state["class"] not in classes():
            raise WireError("Unknown fixed instruction class")
        validate_attributes(state, index, ATTRS)
        name_value(state["_name"])
        integer(state["_num_qubits"], 512)
        integer(state["_num_clbits"], 512)
        node(state["_params"], index, {"list"})
        if state["_definition"] is not None:
            node(state["_definition"], index, {"quantum_circuit"})
        if state["_label"] is not None:
            name_value(state["_label"])

    def tokens(self, state):
        return (state["attributes"],) + tuple(state[key] for key, _ in ATTRS)

    def allocate(self, state, index):
        return object.__new__(classes()[state["class"]])

    def prepare(self, state, resolve, index):
        return resolve(state["attributes"]["ref"])

    def apply(self, target, prepared):
        object.__setattr__(target, "__dict__", prepared)

    def validate_update(self, previous, state):
        if previous["class"] != state["class"]:
            raise WireError("Instruction class cannot change")

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()

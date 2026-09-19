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

CONTROL_ATTRS = ATTRS + tuple(
    (key, key) for key in ("base_gate", "_num_ctrl_qubits", "_ctrl_state", "_open_ctrl")
)


def attributes(selector):
    from qiskit.circuit import ControlledGate

    return CONTROL_ATTRS if issubclass(classes()[selector], ControlledGate) else ATTRS


@cache
def classes():
    from qiskit.circuit import ControlledGate, Gate, Instruction
    from qiskit.circuit.library import MCXGate, get_standard_gate_name_mapping

    result = {
        "gate": Gate,
        "instruction": Instruction,
        "controlled": ControlledGate,
        "mcx": MCXGate,
    }
    expected = {key for key, _ in ATTRS}
    for name, template in get_standard_gate_name_mapping().items():
        if set(vars(template)) in (expected, {key for key, _ in CONTROL_ATTRS}):
            result["standard:" + name] = template.base_class
    return result


@dataclass(frozen=True)
class InstructionCodec:
    kind: str = "python_instruction"
    immutable: bool = False

    def matches(self, value):
        return type(value) in classes().values()

    def state(self, value, ref):
        selector = next(key for key, cls in classes().items() if type(value) is cls)
        attrs = attributes(selector)
        if set(vars(value)) != {key for key, _ in attrs}:
            raise WireError("Extra or missing instruction fields require another codec")
        return {
            "class": selector,
            "attributes": ref(vars(value)),
            **{key: ref(vars(value)[key]) for key, _ in attrs},
        }

    def validate(self, state, index):
        if (
            type(state) is not dict
            or type(state.get("class")) is not str
            or state["class"] not in classes()
        ):
            raise WireError("Unknown fixed instruction class")
        attrs = attributes(state["class"])
        fields(state, {"class", "attributes"} | {key for key, _ in attrs})
        validate_attributes(state, index, attrs)
        if attrs is CONTROL_ATTRS:
            count = integer(state["_num_ctrl_qubits"], 512)
            integer(state["_ctrl_state"], (1 << count) - 1)
            if type(state["_open_ctrl"]) is not bool:
                raise WireError("Invalid raw open-control flag")
            current, seen = state, set()
            for _ in range(32):
                if "base_gate" not in current:
                    break
                base = node(current["base_gate"], index, {"python_instruction"})
                handle = current["base_gate"]["ref"]
                if handle in seen:
                    raise WireError("Cyclic controlled base graph is unsupported")
                seen.add(handle)
                current = base["state"]
                if type(current) is not dict:
                    raise WireError("Invalid controlled base state")
            else:
                raise WireError("Controlled base nesting exceeds limit")
        name_value(state["_name"])
        integer(state["_num_qubits"], 512)
        integer(state["_num_clbits"], 512)
        node(state["_params"], index, {"list", "qiskit_frozen_list"})
        if state["_definition"] is not None:
            node(state["_definition"], index, {"quantum_circuit"})
        if state["_label"] is not None:
            name_value(state["_label"])

    def tokens(self, state):
        return (state["attributes"],) + tuple(state[key] for key, _ in attributes(state["class"]))

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

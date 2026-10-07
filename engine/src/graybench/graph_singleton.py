"""Closed singleton state; allocation is private, public binding is explicit."""

from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError
from graybench.graph_instruction import InstructionCodec, attributes


@cache
def singleton_classes():
    from qiskit.circuit.library import get_standard_gate_name_mapping

    return {
        name: type(value)
        for name, value in sorted(get_standard_gate_name_mapping().items())
        if not value.mutable
    }


@dataclass(frozen=True)
class SingletonCodec(InstructionCodec):
    kind: str = "public_singleton"

    def matches(self, value):
        return type(value) in singleton_classes().values()

    def state(self, value, ref):
        factory = next(k for k, cls in singleton_classes().items() if type(value) is cls)
        attrs = attributes("standard:" + factory)
        if set(vars(value)) != {key for key, _ in attrs}:
            raise WireError("Extra or missing singleton fields require another codec")
        return {
            "factory": factory,
            "attributes": ref(vars(value)),
            **{key: ref(vars(value)[key]) for key, _ in attrs},
        }

    def validate(self, state, index):
        if (
            type(state) is not dict
            or type(state.get("factory")) is not str
            or state["factory"] not in singleton_classes()
        ):
            raise WireError("Unknown fixed singleton factory")
        converted = dict(state)
        converted["class"] = "standard:" + converted.pop("factory")
        super().validate(converted, index)

    def tokens(self, state):
        return (state["attributes"],) + tuple(
            state[key] for key, _ in attributes("standard:" + state["factory"])
        )

    def allocate(self, state, index):
        return object.__new__(singleton_classes()[state["factory"]])

    def validate_update(self, previous, state):
        if previous["factory"] != state["factory"]:
            raise WireError("Singleton runtime class cannot change")

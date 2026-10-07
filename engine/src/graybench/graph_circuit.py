"""Initial circuit graph members: immutable register-owned bit values and wrappers.

Anonymous bits require a session-wide equality mapping: restoring their integer
IDs does not advance Qiskit's allocator and can collide with new local bits.
They remain explicitly unsupported. No circuit serialization fallback is used.
"""

from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError, fields, integer
from graybench.graph_symbolic import name_value


@cache
def member_classes():
    from qiskit.circuit import (
        AncillaQubit,
        AncillaRegister,
        ClassicalRegister,
        Clbit,
        QuantumRegister,
        Qubit,
    )

    return (
        {"q": Qubit, "c": Clbit, "a": AncillaQubit},
        {"q": QuantumRegister, "c": ClassicalRegister, "a": AncillaRegister},
    )


def tag(value, types):
    for name, cls in types.items():
        if type(value) is cls:
            return name
    raise WireError("Unsupported circuit member class")


def bit_state(value):
    family = tag(value, member_classes()[0])
    owner = value._register
    if owner is None:
        raise WireError("Anonymous bit equality requires a session identity codec")
    return {"family": family, "name": owner.name, "size": owner.size, "index": value._index}


def validate_bit(state):
    fields(state, {"family", "name", "size", "index"})
    validate_identity(state, member_classes()[0])
    index = integer(state["index"], 511)
    if index >= state["size"]:
        raise WireError("Owned bit index is outside its register")


def validate_identity(state, types):
    if type(state["family"]) is not str or state["family"] not in types:
        raise WireError("Invalid fixed circuit member family")
    name_value(state["name"])
    integer(state["size"], 512)


def restore_bit(state):
    return member_classes()[0][state["family"]]._from_owned(
        state["name"], state["size"], state["index"]
    )


@dataclass(frozen=True)
class MemberCodec:
    kind: str
    immutable: bool = True

    def matches(self, value):
        types = member_classes()[self.kind == "qiskit_register"]
        return type(value) in types.values()

    def state(self, value, ref):
        if self.kind == "qiskit_bit":
            return bit_state(value)
        family = tag(value, member_classes()[1])
        _, _, bits = value.__getnewargs__()
        return {
            "family": family,
            "name": value.name,
            "size": value.size,
            "bits": None if bits is None else [bit_state(bit) for bit in bits],
        }

    def validate(self, state, index):
        if self.kind == "qiskit_bit":
            validate_bit(state)
            return
        fields(state, {"family", "name", "size", "bits"})
        validate_identity(state, member_classes()[1])
        bits = state["bits"]
        if bits is not None:
            if type(bits) is not list or len(bits) != state["size"]:
                raise WireError("Alias register member count differs from size")
            for bit in bits:
                validate_bit(bit)
                allowed = {"q", "a"} if state["family"] == "q" else {state["family"]}
                if bit["family"] not in allowed:
                    raise WireError("Alias register contains an incompatible bit type")

    def allocate(self, state, index):
        from qiskit.exceptions import QiskitError

        try:
            if self.kind == "qiskit_bit":
                return restore_bit(state)
            cls = member_classes()[1][state["family"]]
            if state["bits"] is None:
                return cls(state["size"], state["name"])
            return cls(name=state["name"], bits=[restore_bit(bit) for bit in state["bits"]])
        except (ValueError, TypeError, OverflowError, QiskitError) as exc:
            raise WireError("Invalid circuit member reconstruction") from exc

    def tokens(self, state):
        return ()

    def validate_update(self, previous, state):
        pass

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()


CIRCUIT_CODECS = {name: MemberCodec(name) for name in ("qiskit_bit", "qiskit_register")}

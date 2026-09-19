"""Native CircuitData membership and owner-created cache nodes.

Instruction streams and runtime variables are separate unfinished capabilities.
This codec currently admits empty instruction streams and finite numeric phase.
"""

import math
from dataclasses import dataclass

from graybench.circuit_wire import WireError, fields, integer
from graybench.graph_circuit import CIRCUIT_CODECS, bit_state, restore_bit, validate_bit
from graybench.graph_scientific import node

SLOTS = {
    "qubits_cache": ("qubits", "list"),
    "clbits_cache": ("clbits", "list"),
    "qubit_indices": ("_qubit_indices", "dict"),
    "clbit_indices": ("_clbit_indices", "dict"),
}
REGISTER = CIRCUIT_CODECS["qiskit_register"]


@dataclass(frozen=True)
class CircuitDataCodec:
    kind: str = "circuit_data"
    immutable: bool = False

    def matches(self, value):
        from qiskit._accelerate.circuit import CircuitData

        return type(value) is CircuitData

    def state(self, value, ref):
        if len(value) or any(
            getattr(value, "num_" + name)
            for name in (
                "input_vars",
                "captured_vars",
                "declared_vars",
                "captured_stretches",
                "declared_stretches",
            )
        ):
            raise WireError("CircuitData operations/variables require further graph codecs")
        intrinsic = value.copy_empty_like()
        state = {
            "qubits": [bit_state(bit) for bit in intrinsic.qubits],
            "clbits": [bit_state(bit) for bit in intrinsic.clbits],
            "qregs": [REGISTER.state(reg, ref) for reg in value.qregs],
            "cregs": [REGISTER.state(reg, ref) for reg in value.cregs],
            "phase": value.global_phase,
        }
        state.update({key: ref(getattr(value, attr)) for key, (attr, _) in SLOTS.items()})
        return state

    def validate(self, state, index):
        fields(state, {"qubits", "clbits", "qregs", "cregs", "phase"} | set(SLOTS))
        for name, families in (("qubits", {"q", "a"}), ("clbits", {"c"})):
            items = state[name]
            if type(items) is not list or len(items) > 512:
                raise WireError("Invalid or excessive intrinsic membership")
            seen = set()
            for item in items:
                validate_bit(item)
                if item["family"] not in families:
                    raise WireError("Invalid intrinsic bit family")
                key = (item["family"], item["name"], item["size"], item["index"])
                if key in seen:
                    raise WireError("Duplicate intrinsic bit")
                seen.add(key)
        for name, families in (("qregs", {"q", "a"}), ("cregs", {"c"})):
            if type(state[name]) is not list or len(state[name]) > 512:
                raise WireError("Invalid intrinsic register list")
            for item in state[name]:
                REGISTER.validate(item, index)
                if item["family"] not in families:
                    raise WireError("Invalid intrinsic register family")
        phase = state["phase"]
        if type(phase) is not float or not math.isfinite(phase) or not 0 <= phase < math.tau:
            raise WireError("CircuitData requires a canonical finite numeric phase")
        for key, (_, kind) in SLOTS.items():
            node(state[key], index, {kind})

    def allocate(self, state, index):
        from qiskit._accelerate.circuit import CircuitData
        from qiskit.exceptions import QiskitError

        try:
            data = CircuitData(
                qubits=[restore_bit(x) for x in state["qubits"]],
                clbits=[restore_bit(x) for x in state["clbits"]],
            )
            for family in ("qregs", "cregs"):
                for reg in state[family]:
                    getattr(data, "add_qreg" if family == "qregs" else "add_creg")(
                        REGISTER.allocate(reg, index)
                    )
            if data.num_qubits != len(state["qubits"]) or data.num_clbits != len(state["clbits"]):
                raise WireError("Register membership introduces undeclared bits")
            return data
        except (ValueError, TypeError, QiskitError) as exc:
            raise WireError("Invalid intrinsic CircuitData state") from exc

    def transition_owner(self, value, previous, state, index):
        from qiskit.exceptions import QiskitError

        try:
            for bits, regs, cache in (
                ("qubits", "qregs", "qubits_cache"),
                ("clbits", "cregs", "clbits_cache"),
            ):
                old_regs, new_regs = previous[regs], state[regs]
                if new_regs[: len(old_regs)] != old_regs:
                    raise WireError(
                        "Register removal/replacement requires another owner transition"
                    )
                if previous[bits] != state[bits] or previous[cache] != state[cache]:
                    value.replace_bits(**{bits: [restore_bit(bit) for bit in state[bits]]})
                for reg in new_regs[len(old_regs) :]:
                    getattr(value, "add_qreg" if regs == "qregs" else "add_creg")(
                        REGISTER.allocate(reg, index)
                    )
            if value.num_qubits != len(state["qubits"]) or value.num_clbits != len(state["clbits"]):
                raise WireError("Owner transition changed undeclared membership")
        except (ValueError, TypeError, QiskitError) as exc:
            raise WireError("Unsupported CircuitData owner transition") from exc

    def owner_children(self, value, state):
        return {state[key]["ref"]: getattr(value, attr) for key, (attr, _) in SLOTS.items()}

    def tokens(self, state):
        return tuple(state[key] for key in SLOTS)

    def prepare(self, state, resolve, index):
        return state["phase"]

    def apply(self, target, prepared):
        target.global_phase = prepared

    def validate_update(self, previous, state):
        pass

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()


@dataclass(frozen=True)
class BitLocationsCodec:
    kind: str = "bit_locations"
    immutable: bool = True

    def matches(self, value):
        from qiskit._accelerate.circuit import BitLocations

        return type(value) is BitLocations

    def state(self, value, ref):
        return {"index": value.index, "registers": ref(value.registers)}

    def validate(self, state, index):
        fields(state, {"index", "registers"})
        integer(state["index"], 511)
        node(state["registers"], index, {"list"})

    def tokens(self, state):
        return (state["registers"],)

    def allocate(self, state, index):
        return None

    def populate(self, target, state, resolve):
        from qiskit._accelerate.circuit import BitLocations

        return BitLocations(state["index"], resolve(state["registers"]["ref"]))

    def validate_update(self, previous, state):
        pass

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()


CIRCUIT_DATA_CODECS = {"circuit_data": CircuitDataCodec(), "bit_locations": BitLocationsCodec()}

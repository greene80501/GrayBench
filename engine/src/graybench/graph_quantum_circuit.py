"""Fixed Python circuit components; native instruction storage is a separate node."""

from dataclasses import dataclass
from functools import cache

from graybench.circuit_wire import WireError, fields, integer
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
    "transpile_layout": tuple(
        (key, key)
        for key in (
            "initial_layout",
            "input_qubit_mapping",
            "final_layout",
            "_input_qubit_count",
            "_output_qubit_list",
        )
    ),
}
LAYOUT_SLOTS = ("_p2v", "_regs", "_v2p")
LATENCIES = ("_clbit_write_latency", "_conditional_latency")
QFT_FIELDS = (
    "_is_initialized",
    "_qregs",
    "_cregs",
    "_is_built",
    "_approximation_degree",
    "_do_swaps",
    "_insert_barriers",
    "_inverse",
)


@cache
def circuit_subclasses():
    from qiskit.circuit.library import QFT, GraphState

    return {"qft": QFT, "graph_state": GraphState}


def attributes(kind, values, selector=None):
    return (
        ATTRS[kind]
        + (
            tuple((key, key) for key in LATENCIES if key in values)
            if kind == "quantum_circuit"
            else ()
        )
        + (tuple((key, key) for key in QFT_FIELDS) if selector == "qft" else ())
    )


def quantum_member(token, index, kind="qiskit_bit"):
    value = node(token, index, {kind})
    if value["state"]["family"] not in ("q", "a"):
        raise WireError("Layout requires quantum members")


def mapping_entries(token, index):
    entries = node(token, index, {"dict"})["state"]
    if type(entries) is not list or any(type(x) is not list or len(x) != 2 for x in entries):
        raise WireError("Invalid layout mapping")
    return entries


@cache
def classes():
    from qiskit import QuantumCircuit
    from qiskit.circuit.quantumcircuit import _OuterCircuitScopeInterface
    from qiskit.circuit.quantumcircuitdata import QuantumCircuitData
    from qiskit.transpiler import Layout, TranspileLayout

    return {
        "quantum_circuit": QuantumCircuit,
        "circuit_scope": _OuterCircuitScopeInterface,
        "circuit_data_view": QuantumCircuitData,
        "layout": Layout,
        "transpile_layout": TranspileLayout,
    }


@dataclass(frozen=True)
class CircuitComponentCodec:
    kind: str
    immutable: bool = False

    def matches(self, value):
        return type(value) is classes()[self.kind] or (
            self.kind == "quantum_circuit" and type(value) in circuit_subclasses().values()
        )

    def state(self, value, ref):
        if self.kind == "circuit_scope":
            return {"circuit": ref(value.circuit)}
        if self.kind == "layout":
            return {key: ref(getattr(value, key)) for key in LAYOUT_SLOTS}
        selector = (
            next((name for name, cls in circuit_subclasses().items() if type(value) is cls), None)
            if self.kind == "quantum_circuit"
            else None
        )
        attrs = attributes(self.kind, vars(value), selector)
        expected = {key for key, _ in attrs}
        if set(vars(value)) != expected:
            raise WireError("Extra or missing circuit instance fields are unsupported")
        return {
            **({"class": selector} if selector is not None else {}),
            **{key: ref(vars(value)[attr]) for key, attr in attrs},
            "attributes": ref(vars(value)),
        }

    def validate(self, state, index):
        if self.kind == "circuit_scope":
            fields(state, {"circuit"})
            node(state["circuit"], index, {"quantum_circuit"})
            return
        if self.kind == "layout":
            fields(state, set(LAYOUT_SLOTS))
            for position, bit in mapping_entries(state["_p2v"], index):
                integer(position, 511)
                if bit is not None:
                    quantum_member(bit, index)
            for bit, position in mapping_entries(state["_v2p"], index):
                quantum_member(bit, index)
                integer(position, 511)
            for register in node(state["_regs"], index, {"list"})["state"]:
                quantum_member(register, index, "qiskit_register")
            return
        selector = state.get("class") if type(state) is dict else None
        if selector is not None and (
            self.kind != "quantum_circuit"
            or type(selector) is not str
            or selector not in circuit_subclasses()
        ):
            raise WireError("Unknown fixed circuit class")
        attrs = attributes(self.kind, state, selector)
        fields(
            state,
            {key for key, _ in attrs}
            | {"attributes"}
            | ({"class"} if selector is not None else set()),
        )
        validate_attributes(state, index, attrs)
        if selector == "qft":
            for key in (
                "_is_initialized",
                "_is_built",
                "_do_swaps",
                "_insert_barriers",
                "_inverse",
            ):
                if type(state[key]) is not bool:
                    raise WireError("Invalid raw QFT flag")
            if type(state["_approximation_degree"]) is not int:
                raise WireError("Invalid raw QFT approximation degree")
            for key in ("_qregs", "_cregs"):
                node(state[key], index, {"list"})
        if self.kind == "transpile_layout":
            for key in ("initial_layout", "final_layout"):
                if state[key] is not None:
                    node(state[key], index, {"layout"})
            for bit, position in mapping_entries(state["input_qubit_mapping"], index):
                quantum_member(bit, index)
                integer(position, 511)
            if state["_input_qubit_count"] is not None:
                integer(state["_input_qubit_count"], 512)
            if state["_output_qubit_list"] is not None:
                for bit in node(state["_output_qubit_list"], index, {"list"})["state"]:
                    quantum_member(bit, index)
            return
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
            node(state["_layout"], index, {"transpile_layout"})
        if state["_op_start_times"] is not None:
            node(state["_op_start_times"], index, {"list"})
        duration = state["_duration"]
        if duration is not None and type(duration) not in (float, int):
            raise WireError("Unsupported circuit duration component")
        for key in LATENCIES:
            if key in state and state[key] is not None and type(state[key]) not in (int, float):
                raise WireError("Unsupported circuit latency component")

    def tokens(self, state):
        if self.kind == "circuit_scope":
            return (state["circuit"],)
        if self.kind == "layout":
            return tuple(state[key] for key in LAYOUT_SLOTS)
        return tuple(state[key] for key, _ in attributes(self.kind, state, state.get("class"))) + (
            state["attributes"],
        )

    def allocate(self, state, index):
        if self.kind == "quantum_circuit" and "class" in state:
            return object.__new__(circuit_subclasses()[state["class"]])
        return object.__new__(classes()[self.kind])

    def prepare(self, state, resolve, index):
        if self.kind == "layout":
            return tuple(resolve(state[key]["ref"]) for key in LAYOUT_SLOTS)
        return resolve(
            state["circuit"]["ref"] if self.kind == "circuit_scope" else state["attributes"]["ref"]
        )

    def apply(self, target, prepared):
        if self.kind == "circuit_scope":
            object.__setattr__(target, "circuit", prepared)
        elif self.kind == "layout":
            for key, value in zip(LAYOUT_SLOTS, prepared, strict=True):
                object.__setattr__(target, key, value)
        else:
            object.__setattr__(target, "__dict__", prepared)

    def validate_update(self, previous, state):
        if previous.get("class") != state.get("class"):
            raise WireError("Circuit class cannot change")

    def array_bytes(self, state):
        return 0

    def matrix_refs(self, state):
        return ()


QUANTUM_CIRCUIT_CODECS = {
    kind: CircuitComponentCodec(kind)
    for kind in (
        "quantum_circuit",
        "circuit_scope",
        "circuit_data_view",
        "layout",
        "transpile_layout",
    )
}

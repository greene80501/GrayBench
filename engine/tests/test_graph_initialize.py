import json
import os

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import Initialize, StatePreparation, XGate
from qiskit.quantum_info import DensityMatrix, Statevector

from graybench.circuit_wire import WireError, WireLimitError
from graybench.graph_wire import GraphArena, GraphLimits, wire_bytes


def arenas(public=False, limits=None):
    from graybench.graph_anchors import PublicAnchorRegistry

    anchors = PublicAnchorRegistry.capture() if public else None
    return tuple(
        GraphArena(side=side, session="initialize", limits=limits or GraphLimits(), anchors=anchors)
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    wire = json.loads(wire_bytes(sender.snapshot({"value": value}, sequence=sequence)))
    return receiver.commit(receiver.prepare(wire, sequence=sequence))["value"]


@pytest.mark.parametrize("mode", ["list", "array", "statevector", "label", "integer", "normalize"])
def test_initialize_roundtrip_preserves_wrapper_internal_preparation_and_density(mode):
    expected = np.array([1, 1j], dtype=complex) / np.sqrt(2)
    kwargs = {}
    if mode in ("label", "integer"):
        expected = np.array([0, 1, 0, 0], dtype=complex)
        argument = "01" if mode == "label" else 1
        kwargs = {"num_qubits": 2} if mode == "integer" else {}
    elif mode == "normalize":
        argument = [2, 2j]
        kwargs = {"normalize": True}
    else:
        argument = {
            "list": expected.tolist(),
            "array": expected.copy(),
            "statevector": Statevector(expected),
        }[mode]
    operation = Initialize(argument, **kwargs)
    operation.label = "declared-label"
    circuit = QuantumCircuit(operation.num_qubits)
    circuit.append(operation, circuit.qubits, copy=False)
    sender, receiver = arenas()
    remote, held, preparation, attrs, prep_attrs, params, original = transfer(
        sender,
        receiver,
        (
            circuit,
            operation,
            operation._stateprep,
            vars(operation),
            vars(operation._stateprep),
            operation.params,
            operation._stateprep._params_arg,
        ),
    )
    assert type(held) is Initialize and type(preparation) is StatePreparation
    assert remote.data[0].operation is held and held._stateprep is preparation
    assert vars(held) is attrs and vars(preparation) is prep_attrs
    assert held.params is preparation.params is params
    assert held._definition is preparation._definition is None
    if mode in ("list", "array", "statevector"):
        assert preparation._params_arg is original
    assert remote.data[0].label == held.label == "declared-label"
    np.testing.assert_allclose(
        DensityMatrix.from_instruction(remote).data,
        np.outer(expected, expected.conj()),
        atol=1e-14,
        rtol=0,
    )


def test_initialize_keeps_distinct_native_caches_and_actual_parameter_aliases():
    operation = Initialize([1, 0])
    first, second = QuantumCircuit(1), QuantumCircuit(1)
    first.append(operation, [0], copy=False)
    operation.params = [0, 1]
    second.append(operation, [0], copy=False)
    operation.params = [1 / np.sqrt(2), 1j / np.sqrt(2)]
    operation.name = "changed"
    operation._params = ["raw-unread-cache"]
    actual_params = operation.params
    sender, receiver = arenas()
    x, y, held, internal, params, raw = transfer(
        sender,
        receiver,
        (first, second, operation, operation._stateprep, operation.params, operation._params),
    )
    assert x.data[0].operation is y.data[0].operation is held
    assert held._stateprep is internal and held.params is internal.params is params
    assert held._params is raw and raw == ["raw-unread-cache"]
    assert x.data[0].params == [1, 0] and y.data[0].params == [0, 1]
    assert x.data[0].name == y.data[0].name == "initialize" and held.name == "changed"
    old_params = params
    held.params = [0, 1]
    old_params[0] = 0.3
    returned = transfer(receiver, sender, (held, old_params, x, y))
    assert returned[0] is operation and returned[1] is actual_params
    assert actual_params[0] == 0.3
    assert operation.params == [0, 1] and operation.params is not returned[1]
    assert first.data[0].params == [1, 0] and second.data[0].params == [0, 1]


def test_two_initialize_wrappers_share_preparation_without_merging_native_caches():
    first, second = Initialize([1, 0]), Initialize([0, 1])
    circuit = QuantumCircuit(1)
    circuit.append(first, [0], copy=False)
    circuit.append(second, [0], copy=False)
    second._stateprep = first._stateprep
    original = first._stateprep
    sender, receiver = arenas()
    remote, a, b, prep = transfer(sender, receiver, (circuit, first, second, original))
    assert a is not b and a._stateprep is b._stateprep is prep
    assert remote.data[0].params == [1, 0] and remote.data[1].params == [0, 1]
    b._stateprep = StatePreparation([0, 1])
    transfer(receiver, sender, (a, b))
    assert first._stateprep is original and second._stateprep is not original
    assert first.params == [1, 0] and second.params == [0, 1]
    assert circuit.data[0].params == [1, 0] and circuit.data[1].params == [0, 1]


@pytest.mark.parametrize("cached", [False, True])
def test_initialize_definition_is_preserved_without_forcing_synthesis(cached):
    operation = Initialize("01")
    definition = operation.definition if cached else None
    # Cached definitions contain immutable Reset; production uses public anchors.
    sender, receiver = arenas(public=cached)
    held, prep, body = transfer(sender, receiver, (operation, operation._stateprep, definition))
    assert held._definition is body
    assert prep._definition is None
    if cached:
        assert body.data[-1].operation is prep
        body.x(0)
        assert transfer(receiver, sender, held) is operation
        assert operation._definition is definition and len(definition.data) == 4
    else:
        assert operation._definition is None


@pytest.mark.parametrize("mode", ["label", "W"])
def test_fully_synthesized_initialize_preserves_cached_definitions_and_density(mode):
    vector = np.zeros(8, dtype=complex)
    vector[[1, 2, 4]] = 1 / np.sqrt(3)
    operation = Initialize("001" if mode == "label" else vector)
    if mode == "label":
        vector[:] = 0
        vector[1] = 1
    circuit = QuantumCircuit(3)
    circuit.append(operation, range(3), copy=False)
    DensityMatrix.from_instruction(circuit)  # Populate both SDK synthesis caches.
    sender, receiver = arenas(
        public=True, limits=GraphLimits(message_bytes=16 * 1024 * 1024, depth=128)
    )
    remote, held, prep, outer, inner = transfer(
        sender,
        receiver,
        (
            circuit,
            operation,
            operation._stateprep,
            operation._definition,
            operation._stateprep._definition,
        ),
    )
    assert remote.data[0].operation is held and held._stateprep is prep
    assert held._definition is outer and prep._definition is inner
    np.testing.assert_allclose(
        DensityMatrix.from_instruction(remote).data,
        np.outer(vector, vector.conj()),
        atol=1e-14,
        rtol=0,
    )


def test_extra_initialize_fields_are_explicitly_unsupported():
    operation = Initialize([1, 0])
    operation.extra = "unregistered"
    sender, _ = arenas()
    with pytest.raises(WireError, match="Extra or missing instruction fields"):
        sender.snapshot({"value": operation}, sequence=1)


@pytest.mark.parametrize("replacement", [None, XGate().to_mutable()])
def test_initialize_internal_preparation_must_have_fixed_registered_role(replacement):
    operation = Initialize([1, 0])
    operation._stateprep = replacement
    sender, receiver = arenas()
    with pytest.raises(WireError):
        transfer(sender, receiver, operation)


@pytest.mark.parametrize("fault", ["missing", "wrong-role", "self", "extra", "none", "list"])
def test_invalid_initialize_update_does_not_mutate_live_aliases(fault):
    operation = Initialize([1, 0])
    sender, receiver = arenas()
    held, prep = transfer(sender, receiver, (operation, operation._stateprep))
    operation.params = [0, 1]
    wire = sender.snapshot({"value": (operation, XGate().to_mutable())}, sequence=2)
    index = {row["id"]: row for row in wire["nodes"]}
    record = next(
        row
        for row in wire["nodes"]
        if row["kind"] == "python_instruction" and row["state"]["class"] == "initialize"
    )
    state = record["state"]
    if fault in ("none", "list"):
        index[state["_stateprep"]["ref"]]["state"] = None if fault == "none" else []
    elif fault == "extra":
        state["extra"] = 1
    else:
        token = {
            "missing": {"ref": "j:999999"},
            "self": {"ref": record["id"]},
            "wrong-role": next(
                {"ref": row["id"]}
                for row in wire["nodes"]
                if row["kind"] == "python_instruction" and row["state"]["class"] == "standard:x"
            ),
        }[fault]
        state["_stateprep"] = token
        attrs = index[state["attributes"]["ref"]]["state"]
        next(pair for pair in attrs if pair[0] == "_stateprep")[1] = token
    with pytest.raises(WireError):
        receiver.prepare(wire, sequence=2)
    assert held._stateprep is prep and held.params is prep.params and held.params == [1, 0]


def test_failed_native_cache_reconstruction_restores_both_raw_dictionaries(monkeypatch):
    import qiskit.circuit

    from graybench.graph_python_ops import restore_python

    operation = Initialize([1, 0])
    circuit = QuantumCircuit(1)
    circuit.append(operation, [0], copy=False)
    operation.params = [0, 1]
    sender, _ = arenas()
    wire = sender.snapshot({"value": circuit}, sequence=1)
    record = next(row for row in wire["nodes"] if row["kind"] == "circuit_data")
    insertion = record["state"]["operations"][0]
    attrs, prep_attrs, params = vars(operation), vars(operation._stateprep), operation.params

    def fail(value, *_args):
        assert value.params == [1, 0]
        raise ValueError("Injected native insertion failure")

    monkeypatch.setattr(qiskit.circuit, "CircuitInstruction", fail)
    with pytest.raises(ValueError, match="insertion failure"):
        restore_python(insertion, circuit.qubits, circuit.clbits, sender._objects.__getitem__)
    assert vars(operation) is attrs and vars(operation._stateprep) is prep_attrs
    assert operation.params is params and params == [0, 1]


def test_initialize_original_array_obeys_existing_storage_budget():
    operation = Initialize(np.array([1, 0], dtype=complex))
    sender = GraphArena(
        side="judge", session="initialize-budget", limits=GraphLimits(array_bytes=16)
    )
    with pytest.raises(WireLimitError):
        sender.snapshot({"value": operation}, sequence=1)


@pytest.mark.parametrize("candidate_created", [False, True])
def test_delta_call_preserves_initialize_aliases_and_native_cache(candidate_created):
    from graybench.graph_delta import DeltaGraphArena
    from graybench.graph_rpc import validate_root_shapes

    sender, receiver = (DeltaGraphArena(arena, wire_limit=65536) for arena in arenas(public=True))
    operation = Initialize([1, 0])
    circuit = QuantumCircuit(1)
    circuit.append(operation, [0], copy=False)
    args = () if candidate_created else (circuit, operation)
    request = sender.snapshot({"args": args, "kwargs": {}}, sequence=1)
    prepared = receiver.prepare(json.loads(wire_bytes(request)), sequence=1)
    validate_root_shapes(prepared.snapshot)
    roots = receiver.commit(prepared)
    if not candidate_created:
        circuit, operation = roots["args"]
    operation.params = [0, 1]
    result = (circuit, operation, operation._stateprep, operation.params)
    response = receiver.snapshot({**roots, "result": result, "exception_args": None}, sequence=1)
    prepared = sender.prepare(json.loads(wire_bytes(response)), sequence=1)
    validate_root_shapes(prepared.snapshot, response=True, raised=None)
    returned, held, prep, params = sender.commit(prepared)["result"]
    assert returned.data[0].operation is held and held._stateprep is prep
    assert held.params is prep.params is params and params == [0, 1]
    assert returned.data[0].params == [1, 0]
    if not candidate_created:
        assert returned is args[0] and held is args[1]


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Immutable image required")
def test_protected_initialize_keeps_native_and_python_params_separate():
    from test_graph_bridge import judge

    result = judge(
        """from qiskit.circuit.library import Initialize, StatePreparation
def check(candidate):
    circuit, operation, preparation, params = candidate()
    assert type(operation) is Initialize and type(preparation) is StatePreparation
    assert circuit.data[0].operation is operation
    assert operation._stateprep is preparation
    assert operation.params is preparation.params is params
    assert circuit.data[0].params == [1,0]
    assert operation.params == [0,1]
""",
        """from qiskit import QuantumCircuit
from qiskit.circuit.library import Initialize
def answer():
    operation = Initialize([1,0])
    circuit = QuantumCircuit(1)
    circuit.append(operation,[0],copy=False)
    operation.params = [0,1]
    return circuit,operation,operation._stateprep,operation.params
""",
    )
    assert result.outcome == "pass", result

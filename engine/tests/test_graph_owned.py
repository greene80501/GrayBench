import copy

import pytest
from qiskit._accelerate.circuit import CircuitData
from qiskit.circuit import QuantumRegister

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="owned", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, seq=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=seq), sequence=seq))["value"]


def test_fresh_owner_binds_lists_maps_and_nested_location_aliases():
    a, b = arenas()
    reg = QuantumRegister(2, "q")
    data = CircuitData(qubits=list(reg))
    data.add_qreg(reg)
    bits, indices = data.qubits, data._qubit_indices
    location = indices[bits[0]]
    remote, held, index_map, loc, registers = transfer(
        a, b, (data, bits, indices, location, location.registers)
    )
    assert remote.qubits is held and remote._qubit_indices is index_map
    assert index_map[held[0]] is loc and loc.registers is registers
    assert transfer(b, a, remote) is data


def test_add_bit_rebinds_new_cache_without_replacing_owner_or_old_aliases():
    a, b = arenas()
    reg = QuantumRegister(3, "q")
    data = CircuitData(qubits=list(reg)[:2])
    original_bits, original_map = data.qubits, data._qubit_indices
    remote, old, old_map = transfer(a, b, (data, original_bits, original_map))
    remote.add_qubit(reg[2])
    fresh = remote.qubits
    result, returned_tuple = transfer(b, a, (remote, (fresh, old)))
    assert result is data and data.num_qubits == 3
    assert returned_tuple[0] is data.qubits and returned_tuple[1] is original_bits
    assert data.qubits is not original_bits and len(original_bits) == len(old) == 2
    assert data._qubit_indices is not original_map and len(original_map) == len(old_map) == 2


def test_equal_membership_replace_changes_cache_ids_and_keeps_detached_tuples():
    a, b = arenas()
    data = CircuitData(qubits=list(QuantumRegister(2, "q")))
    old_tuple = (data.qubits, data._qubit_indices)
    remote, held = transfer(a, b, (data, old_tuple))
    remote.replace_bits(qubits=list(remote.qubits))
    new = (remote.qubits, remote._qubit_indices)
    fresh, old = transfer(b, a, (new, held))
    assert old is old_tuple and fresh[0] is data.qubits
    assert fresh[0] is not old[0] and fresh[1] is not old[1]
    assert fresh[0] == old[0]


def test_owner_cache_contents_can_diverge_from_intrinsic_membership():
    a, b = arenas()
    data = CircuitData(qubits=list(QuantumRegister(2, "q")))
    cache = data.qubits
    cache.pop()
    remote, held = transfer(a, b, (data, cache))
    assert remote.qubits is held and len(held) == 1 and remote.num_qubits == 2
    assert len(remote.copy_empty_like().qubits) == 2


def test_late_invalid_reference_does_not_mutate_live_owner_or_caches():
    a, b = arenas()
    reg = QuantumRegister(3, "q")
    data = CircuitData(qubits=list(reg)[:2])
    remote = transfer(a, b, data)
    cache, indices = remote.qubits, remote._qubit_indices
    data.add_qubit(reg[2])
    wire = a.snapshot({"value": (data, [1])}, sequence=2)
    next(n for n in wire["nodes"] if n["kind"] == "list" and n["state"] == [1])["state"] = [
        {"ref": "j:999"}
    ]
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert remote.num_qubits == 2 and remote.qubits is cache and remote._qubit_indices is indices
    assert len(cache) == 2


def test_preparing_valid_transition_alone_does_not_mutate_live_owner():
    a, b = arenas()
    reg = QuantumRegister(3, "q")
    data = CircuitData(qubits=list(reg)[:2])
    remote = transfer(a, b, data)
    held = remote.qubits
    data.add_qubit(reg[2])
    prepared = b.prepare(a.snapshot({"value": data}, sequence=2), sequence=2)
    assert remote.num_qubits == 2 and remote.qubits is held
    assert b.commit(prepared)["value"] is remote and remote.num_qubits == 3
    assert remote.qubits is not held


def test_owner_cannot_adopt_previously_exported_unattached_list():
    a, b = arenas()
    data = CircuitData(qubits=list(QuantumRegister(2, "q")))
    remote = transfer(a, b, data.qubits)
    with pytest.raises(WireError, match="attach|bind"):
        b.prepare(a.snapshot({"value": data}, sequence=2), sequence=2)
    assert len(remote) == 2


def test_two_owners_cannot_claim_one_cache_id():
    a, b = arenas()
    first = CircuitData(qubits=list(QuantumRegister(1, "a")))
    second = CircuitData(qubits=list(QuantumRegister(1, "b")))
    wire = a.snapshot({"value": (first, second)}, sequence=1)
    owners = [n for n in wire["nodes"] if n["kind"] == "circuit_data"]
    owners[1]["state"]["qubits_cache"] = copy.deepcopy(owners[0]["state"]["qubits_cache"])
    with pytest.raises(WireError, match="owner|bind"):
        b.prepare(wire, sequence=1)


def test_append_register_keeps_bit_cache_but_replaces_index_cache():
    a, b = arenas()
    reg = QuantumRegister(2, "q")
    data = CircuitData(qubits=list(reg))
    remote, held, indices = transfer(a, b, (data, data.qubits, data._qubit_indices))
    remote.add_qreg(reg)
    assert remote.qubits is held
    transfer(b, a, remote)
    assert len(data.qregs) == 1 and data.qubits == held
    assert data._qubit_indices is not indices


@pytest.mark.parametrize("phase", [-1.0, 7.0, 10**400])
def test_noncanonical_owner_phase_rejected_without_live_changes(phase):
    a, b = arenas()
    data = CircuitData(qubits=list(QuantumRegister(1, "q")))
    wire = a.snapshot({"value": data}, sequence=1)
    next(n for n in wire["nodes"] if n["kind"] == "circuit_data")["state"]["phase"] = phase
    with pytest.raises(WireError):
        b.prepare(wire, sequence=1)


def test_dynamic_cache_binding_failure_is_rehearsed_before_live_mutation():
    a, b = arenas()
    reg = QuantumRegister(3, "q")
    data = CircuitData(qubits=list(reg)[:2])
    remote = transfer(a, b, data)
    held, indices = remote.qubits, remote._qubit_indices
    before = a.snapshot({"value": data}, sequence=2)
    old = next(n for n in before["nodes"] if n["kind"] == "circuit_data")["state"]
    data.add_qubit(reg[2])
    wire = a.snapshot({"value": data}, sequence=3)
    new = next(n for n in wire["nodes"] if n["kind"] == "circuit_data")["state"]
    new["qubits_cache"] = old["qubits_cache"]
    with pytest.raises(WireError, match="bind"):
        b.prepare(wire, sequence=3)
    assert remote.num_qubits == 2 and remote.qubits is held and remote._qubit_indices is indices


def test_duplicate_intrinsic_registers_do_not_get_silently_deduplicated():
    a, b = arenas()
    reg = QuantumRegister(1, "q")
    data = CircuitData(qubits=list(reg))
    data.add_qreg(reg)
    wire = a.snapshot({"value": data}, sequence=1)
    state = next(n for n in wire["nodes"] if n["kind"] == "circuit_data")["state"]
    state["qregs"].append(copy.deepcopy(state["qregs"][0]))
    with pytest.raises(WireError):
        b.prepare(wire, sequence=1)


def test_owned_cache_cycle_uses_real_cache_without_placeholder():
    a, b = arenas()
    data = CircuitData(qubits=list(QuantumRegister(1, "q")))
    data.qubits.append((data, data.qubits))
    remote, held = transfer(a, b, (data, data.qubits))
    assert remote.qubits is held and held[-1][0] is remote and held[-1][1] is held
    assert remote.num_qubits == 1


def test_owned_prepared_plan_cannot_be_reused_or_committed_by_other_arena():
    a, b = arenas()
    data = CircuitData(qubits=list(QuantumRegister(1, "q")))
    prepared = b.prepare(a.snapshot({"value": data}, sequence=1), sequence=1)
    foreign = GraphArena(side="candidate", session="owned", limits=GraphLimits())
    with pytest.raises(WireError):
        foreign.commit(prepared)
    remote = b.commit(prepared)["value"]
    with pytest.raises(WireError):
        b.commit(prepared)
    assert remote.num_qubits == 1


def test_classical_membership_transition_binds_only_classical_new_caches():
    from qiskit.circuit import ClassicalRegister

    a, b = arenas()
    qreg = QuantumRegister(1, "q")
    creg = ClassicalRegister(2, "c")
    data = CircuitData(qubits=list(qreg), clbits=[creg[0]])
    remote = transfer(a, b, data)
    qcache, qindices = data.qubits, data._qubit_indices
    old = data.clbits
    remote.add_clbit(creg[1])
    transfer(b, a, remote)
    assert data.qubits is qcache and data._qubit_indices is qindices
    assert data.clbits is not old and data.num_clbits == 2 and len(old) == 1

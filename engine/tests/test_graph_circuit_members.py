import copy

import pytest
from qiskit.circuit import (
    AncillaQubit,
    AncillaRegister,
    ClassicalRegister,
    Clbit,
    QuantumRegister,
    Qubit,
)

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="members", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, seq=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=seq), sequence=seq))["value"]


@pytest.mark.parametrize(
    "register_type,bit_type",
    [
        (QuantumRegister, Qubit),
        (ClassicalRegister, Clbit),
        (AncillaRegister, AncillaQubit),
    ],
)
def test_owned_register_and_bit_identity_matches_native_wrappers(register_type, bit_type):
    a, b = arenas()
    reg = register_type(3, "r")
    bit, equal = reg[1], reg[1]
    assert bit == equal and bit is not equal
    x, y, z, r = transfer(a, b, (bit, equal, bit, reg))
    assert type(x) is bit_type and type(r) is register_type
    assert x == y == r[1] and x is not y and x is z
    assert x._register is not r and x._register == r
    assert transfer(b, a, x) is bit
    assert transfer(a, b, reg, 2) is r


def test_distinct_equal_registers_and_different_names_keep_semantics():
    a, b = arenas()
    first, second, other = (
        QuantumRegister(2, "q"),
        QuantumRegister(2, "q"),
        QuantumRegister(2, "other"),
    )
    x, y, z = transfer(a, b, (first, second, other))
    assert x == y and x is not y and x != z
    assert x[0] == y[0] and x[0] != z[0]


def test_alias_register_preserves_order_and_owned_bit_values_without_invented_aliases():
    a, b = arenas()
    source = QuantumRegister(3, "source")
    members = [source[2], source[0]]
    alias = QuantumRegister(name="alias", bits=members)
    assert alias[0] is not members[0]
    remote, bits = transfer(a, b, (alias, members))
    assert list(remote) == [bits[0], bits[1]]
    assert remote[0] is not bits[0] and remote.name == "alias"
    assert transfer(b, a, remote) is alias


@pytest.mark.parametrize("which", ["bit", "register"])
def test_invalid_owned_member_rejected_before_existing_list_changes(which):
    a, b = arenas()
    values = [1]
    held = transfer(a, b, values)
    values.append(2)
    reg = QuantumRegister(2, "q")
    wire = a.snapshot({"value": (values, reg, reg[0])}, sequence=2)
    record = next(n for n in wire["nodes"] if n["kind"] == "qiskit_" + which)
    record["state"]["size"] = True
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert held == [1]


def test_owned_bit_index_out_of_range_is_rejected():
    a, b = arenas()
    wire = a.snapshot({"value": QuantumRegister(2, "q")[0]}, sequence=1)
    wire["nodes"][0]["state"]["index"] = 2
    with pytest.raises(WireError):
        b.prepare(wire, sequence=1)


def test_existing_owned_bit_cannot_change_value():
    a, b = arenas()
    wire = a.snapshot({"value": QuantumRegister(2, "q")[0]}, sequence=1)
    b.commit(b.prepare(wire, sequence=1))
    changed = copy.deepcopy(wire)
    changed["sequence"] = 2
    changed["nodes"][0]["state"]["index"] = 1
    with pytest.raises(WireError):
        b.prepare(changed, sequence=2)


@pytest.mark.parametrize("value", [Qubit(), Clbit(), AncillaQubit()])
def test_anonymous_bit_identity_is_explicitly_unsupported(value):
    a, _ = arenas()
    with pytest.raises(WireError, match="Anonymous"):
        a.snapshot({"value": value}, sequence=1)


@pytest.mark.parametrize("cls", [QuantumRegister, ClassicalRegister, AncillaRegister])
def test_alias_register_preserves_exact_bit_family(cls):
    a, b = arenas()
    source = cls(2, "source")
    reg = cls(name="alias", bits=[source[1], source[0]])
    remote = transfer(a, b, reg)
    assert type(remote) is cls and list(remote) == list(reg)
    assert type(remote[0]) is type(reg[0])
    assert transfer(b, a, remote) is reg


@pytest.mark.parametrize(
    "bad",
    [
        {"family": "__import__", "name": "q", "size": 2, "index": 0},
        {"family": "q", "name": "\ud800", "size": 2, "index": 0},
        {"family": "q", "name": "q", "size": 513, "index": 0},
        {"family": "q", "name": "q", "size": 2, "index": False},
    ],
)
def test_new_malformed_bit_descriptor_rejected(bad):
    a, b = arenas()
    wire = a.snapshot({"value": QuantumRegister(2, "q")[0]}, sequence=1)
    wire["nodes"][0]["state"] = bad
    with pytest.raises(WireError):
        b.prepare(wire, sequence=1)


def test_alias_register_with_anonymous_members_is_explicitly_unsupported():
    a, _ = arenas()
    alias = QuantumRegister(name="alias", bits=[Qubit()])
    with pytest.raises(WireError, match="Anonymous"):
        a.snapshot({"value": alias}, sequence=1)

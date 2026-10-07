import pytest
from qiskit.circuit.singleton import _frozenlist

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="frozen", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, sequence=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=sequence), sequence=sequence))[
        "value"
    ]


def test_frozen_list_type_and_method_guards_preserved():
    a, b = arenas()
    original = _frozenlist([1])
    remote = transfer(a, b, original)
    assert type(remote) is _frozenlist and list(remote) == [1]
    with pytest.raises(TypeError):
        remote.append(2)
    list.append(remote, 2)
    assert transfer(b, a, remote) is original and list(original) == [1, 2]


def test_frozen_list_cycle_and_shared_child_identity():
    a, b = arenas()
    child = []
    original = _frozenlist([child, child])
    list.append(original, original)
    remote, held = transfer(a, b, (original, child))
    assert remote[0] is remote[1] is held and remote[2] is remote
    held.append("changed")
    transfer(b, a, remote)
    assert child == ["changed"] and original[2] is original


def test_frozen_list_late_dangling_reference_leaves_live_contents():
    a, b = arenas()
    original = _frozenlist([1])
    remote = transfer(a, b, original)
    list.append(original, 2)
    wire = a.snapshot({"value": original}, sequence=2)
    next(n for n in wire["nodes"] if n["kind"] == "qiskit_frozen_list")["state"].append(
        {"ref": "j:999999"}
    )
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert list(remote) == [1]


def test_equal_frozen_lists_remain_distinct_and_detached():
    a, b = arenas()
    first, second = _frozenlist([]), _frozenlist([])
    remote, other = transfer(a, b, (first, second))
    assert remote is not other
    list.append(remote, 1)
    assert transfer(b, a, other) is second and list(first) == [1] and list(second) == []


def test_instruction_preserves_explicit_frozen_parameter_list():
    from qiskit.circuit.library import RXGate

    a, b = arenas()
    gate = RXGate(0.3)
    gate._params = _frozenlist([0.3])
    remote, params = transfer(a, b, (gate, gate.params))
    assert remote.params is params and type(params) is _frozenlist
    with pytest.raises(TypeError):
        params.append(0.4)
    list.__setitem__(params, 0, 0.8)
    assert transfer(b, a, remote) is gate and gate.params == [0.8]

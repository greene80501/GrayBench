import os

import pytest
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap, Layout

from graybench.circuit_wire import WireError
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    return tuple(
        GraphArena(side=s, session="layout", limits=GraphLimits()) for s in ("judge", "candidate")
    )


def transfer(a, b, value, sequence=1):
    return b.commit(b.prepare(a.snapshot({"value": value}, sequence=sequence), sequence=sequence))[
        "value"
    ]


def test_layout_slot_aliases_and_independent_exposed_maps():
    a, b = arenas()
    qc = QuantumCircuit(2)
    layout = Layout({qc.qubits[0]: 2, qc.qubits[1]: 0, 1: None})
    layout.add_register(qc.qregs[0])
    remote, virtual, physical, registers, bit = transfer(
        a, b, (layout, layout._v2p, layout._p2v, layout._regs, qc.qubits[0])
    )
    assert type(remote) is Layout
    assert remote.get_virtual_bits() is virtual and remote.get_physical_bits() is physical
    assert remote._regs is registers and physical[1] is None
    # Native exposed maps can diverge. Transport must not silently repair them.
    virtual[bit] = 1
    assert transfer(b, a, remote) is layout
    assert layout._v2p[qc.qubits[0]] == 1 and layout._p2v[2] == qc.qubits[0]


def test_transpiled_circuit_layout_preserves_actual_separate_wrappers():
    a, b = arenas()
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    result = transpile(
        qc,
        coupling_map=CouplingMap([[0, 1], [1, 0], [1, 2], [2, 1]]),
        initial_layout=[2, 0],
        basis_gates=["u", "cx"],
        optimization_level=0,
        seed_transpiler=7,
    )
    layout = result.layout
    remote, held, attrs, output = transfer(
        a, b, (result, layout, vars(layout), layout._output_qubit_list)
    )
    assert remote.layout is held and vars(held) is attrs
    assert held._output_qubit_list is output and output is not remote.qubits
    assert [x is y for x, y in zip(output, remote.qubits, strict=True)] == [
        x is y for x, y in zip(layout._output_qubit_list, result.qubits, strict=True)
    ]
    assert held.final_index_layout() == layout.final_index_layout()
    assert vars(remote)["_clbit_write_latency"] is None
    assert vars(remote)["_conditional_latency"] is None
    assert transfer(b, a, remote) is result


def test_optional_latency_presence_changes_without_replacing_instance_dictionary():
    a, b = arenas()
    qc = QuantumCircuit(1)
    remote, attrs = transfer(a, b, (qc, vars(qc)))
    assert "_clbit_write_latency" not in attrs
    remote._clbit_write_latency = 3
    remote._conditional_latency = None
    assert transfer(b, a, remote) is qc
    assert qc._clbit_write_latency == 3 and qc._conditional_latency is None
    del qc._conditional_latency
    remote = transfer(a, b, qc, 2)
    assert vars(remote) is attrs and "_conditional_latency" not in attrs


def test_equal_layout_slot_replacement_preserves_detached_map():
    a, b = arenas()
    qc = QuantumCircuit(1)
    layout = Layout({qc.qubits[0]: 0})
    original = layout._v2p
    remote, old, bit = transfer(a, b, (layout, original, qc.qubits[0]))
    remote._v2p = dict(remote._v2p)
    old[bit] = 2
    assert transfer(b, a, remote) is layout
    assert layout._v2p is not original
    assert layout._v2p[qc.qubits[0]] == 0 and original[qc.qubits[0]] == 2


@pytest.mark.parametrize("mutation", ["slot", "physical", "register"])
def test_malformed_layout_is_rejected_before_live_slot_changes(mutation):
    a, b = arenas()
    qc = QuantumCircuit(1)
    layout = Layout({qc.qubits[0]: 0})
    remote = transfer(a, b, layout)
    layout._v2p[qc.qubits[0]] = 2
    wire = a.snapshot({"value": layout}, sequence=2)
    record = next(x for x in wire["nodes"] if x["kind"] == "layout")
    index = {x["id"]: x for x in wire["nodes"]}
    if mutation == "slot":
        record["state"]["_regs"] = record["state"]["_v2p"]
    elif mutation == "physical":
        index[record["state"]["_p2v"]["ref"]]["state"][0][0] = -1
    else:
        index[record["state"]["_regs"]["ref"]]["state"].append(None)
    with pytest.raises(WireError):
        b.prepare(wire, sequence=2)
    assert list(remote._v2p.values()) == [0] and remote._regs == []


@pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires pinned Docker image"
)
def test_actual_protected_transpilation_layout():
    from test_graph_bridge import judge

    result = judge(
        """from qiskit import QuantumCircuit
from qiskit.transpiler import Layout, TranspileLayout
def check(candidate):
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    result = candidate(qc)
    assert result.num_qubits == 3
    assert type(result.layout) is TranspileLayout
    assert type(result.layout.initial_layout) is Layout
    assert len(result.layout.final_index_layout()) == 2
    assert result.layout._output_qubit_list is not result.qubits
    assert all(a is not b for a, b in zip(result.layout._output_qubit_list, result.qubits))
    assert vars(result)['_clbit_write_latency'] is None
""",
        """from qiskit import transpile
from qiskit.transpiler import CouplingMap
def answer(qc):
    return transpile(qc, coupling_map=CouplingMap([[0,1],[1,0],[1,2],[2,1]]),
                     initial_layout=[2,0], basis_gates=['u','cx'], optimization_level=0,
                     seed_transpiler=7)
""",
    )
    assert result.outcome == "pass", result

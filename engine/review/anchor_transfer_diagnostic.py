"""Trusted independent-process anchor round trip; no candidate or hidden judge."""

import copy
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit.library import CXGate, HGate, XGate

import graybench.graph_wire as graph_module
from graybench.circuit_wire import WireError
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_wire import GraphArena, GraphLimits


def peer(mode):
    registry = PublicAnchorRegistry.capture()
    side = "judge" if mode == "origin" else "candidate"
    arena = GraphArena(side=side, session="anchor-probe", limits=GraphLimits(), anchors=registry)
    x = XGate()
    if mode == "origin":
        old_metadata, old_bits = x._definition.metadata, x._definition._data.qubits
        cx = CXGate().to_mutable()
        qc = QuantumCircuit(2)
        qc.append(cx, [0, 1], copy=False)
        vars(x)["_label"] = "sender"
        roots = dict(
            x=x,
            attrs=vars(x),
            params=x.params,
            definition=x._definition,
            metadata=old_metadata,
            bits=old_bits,
            cx=cx,
            qc=qc,
        )
        outgoing = arena.snapshot(roots, sequence=1)
        assert len(outgoing["nodes"]) < registry.manifest()["nodes"]
        print(json.dumps(outgoing), flush=True)
        reply = json.loads(sys.stdin.readline())
        out = arena.commit(arena.prepare(reply, sequence=1))
        assert out["x"] is x and x.label == "receiver"
        assert out["old_metadata"] is old_metadata
        assert out["new_metadata"] is x._definition.metadata is not old_metadata
        assert out["old_bits"] is old_bits
        assert out["new_bits"] is x._definition._data.qubits is not old_bits
        assert out["cx"] is cx and out["qc"] is qc and qc.data[0].operation is cx
        assert cx.base_gate is XGate()
        print(json.dumps({"round_trip": True, "exported_nodes": len(outgoing["nodes"])}))
        return
    incoming = json.load(sys.stdin)
    attrs, params, definition, bits = vars(x), x.params, x._definition, x._definition._data.qubits
    bad = copy.deepcopy(incoming)
    state = next(n for n in bad["nodes"] if n["kind"] == "circuit_data")["state"]
    state["qregs"].append(copy.deepcopy(state["qregs"][0]))
    try:
        arena.prepare(bad, sequence=1)
    except WireError:
        pass
    else:
        raise AssertionError("invalid native-owner state accepted")
    assert vars(x) is attrs and x.label is None and x.params is params
    assert x._definition is definition and definition._data.qubits is bits
    vars(HGate())["_label"] = "unpassed receiver state"
    prepared = arena.prepare(incoming, sequence=1)
    assert x.label is None
    out = arena.commit(prepared)
    assert out["x"] is x and x.label == "sender"
    assert out["attrs"] is vars(x) and out["params"] is x.params
    assert out["definition"] is x._definition and out["bits"] is x._definition._data.qubits
    assert out["cx"].base_gate is x and out["qc"].data[0].operation is out["cx"]
    assert HGate().label == "unpassed receiver state"
    vars(x)["_label"] = "receiver"
    x._definition.metadata = dict(x._definition.metadata)
    x._definition._data.replace_bits(qubits=list(x._definition._data.qubits))
    roots = dict(
        x=x,
        old_metadata=out["metadata"],
        new_metadata=x._definition.metadata,
        old_bits=out["bits"],
        new_bits=x._definition._data.qubits,
        cx=out["cx"],
        qc=out["qc"],
    )
    print(json.dumps(arena.snapshot(roots, sequence=1)))


def main():
    command = [sys.executable, "-B", str(Path(__file__).resolve())]
    with subprocess.Popen(
        command + ["origin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as origin:
        try:
            wire = origin.stdout.readline()
            assert json.loads(wire)["format"] == "call_graph_anchors_v1"
            remote = subprocess.run(
                command + ["remote"], input=wire, capture_output=True, text=True, timeout=45
            )
            assert remote.returncode == 0, remote.stderr
            stdout, stderr = origin.communicate(remote.stdout, timeout=45)
            assert origin.returncode == 0, stderr
            result = json.loads(stdout)
        finally:
            if origin.poll() is None:
                origin.kill()
                origin.communicate()
    names = (
        "graph_wire.py",
        "graph_anchors.py",
        "graph_anchor_bindings.py",
        "graph_singleton.py",
        "graph_types.py",
        "graph_numeric.py",
        "circuit_wire.py",
        "scientific_wire.py",
        "graph_scientific.py",
        "graph_primitive.py",
        "graph_symbolic.py",
        "graph_circuit.py",
        "graph_circuit_data.py",
        "graph_owned.py",
        "graph_quantum_circuit.py",
        "graph_packed.py",
        "graph_instruction.py",
        "graph_python_ops.py",
        "graph_object_arrays.py",
        "graph_expressions.py",
        "symbolic_wire.py",
        "primitive_wire.py",
    )
    source = Path(graph_module.__file__).parent
    print(
        json.dumps(
            {
                "scope": "trusted_graph_anchor_independent_process_round_trip",
                "production_bridge_integrated": False,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "system": platform.system(),
                **result,
                "checks": [
                    "factory_and_child_identity",
                    "controlled_base_and_retained_operation",
                    "late_native_failure_atomicity",
                    "prepare_does_not_apply",
                    "unpassed_factory_unchanged",
                    "replacement_and_detached_alias_round_trip",
                ],
                "source_sha256": {
                    name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in names
                },
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) == 2:
        peer(sys.argv[1])
    else:
        main()

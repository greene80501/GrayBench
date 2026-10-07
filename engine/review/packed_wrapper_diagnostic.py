"""Circuit-only singleton wrapper transfers in independent processes."""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit import CircuitInstruction
from qiskit.circuit.library import CXGate, XGate

import graybench.graph_wire as graph_module
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_wire import GraphArena, GraphLimits


def metadata_owner(gate):
    return gate.base_gate._definition if isinstance(gate, CXGate) else gate._definition


def peer(role, profile):
    registry = PublicAnchorRegistry.capture()
    side = "judge" if role == "origin" else "candidate"
    arena = GraphArena(side=side, session="packed-wrapper", limits=GraphLimits(), anchors=registry)
    if role == "origin":
        gate = CXGate() if profile == "controlled-python" else XGate()
        if profile == "clone":
            gate = object.__new__(type(XGate()))
            object.__setattr__(gate, "__dict__", dict(vars(XGate())))
        if profile == "controlled-python":
            vars(XGate())["_label"] = "native Python at insertion"
        qc = QuantumCircuit(gate.num_qubits)
        qc._data.append(CircuitInstruction(gate, qc.qubits, []))
        qc._data.append(CircuitInstruction(gate, qc.qubits, []))
        if profile == "controlled-python":
            vars(XGate())["_label"] = None
        vars(gate)["_label"] = "sender-visible"
        old = metadata_owner(gate).metadata
        old["probe"] = profile
        outgoing = arena.snapshot({"qc": qc}, sequence=1)
        assert any(n["kind"] == "public_singleton" for n in outgoing["nodes"])
        print(json.dumps(outgoing), flush=True)
        reply = json.loads(sys.stdin.readline())
        out = arena.commit(arena.prepare(reply, sequence=1))
        assert out["qc"] is qc and qc.data[0].operation is qc.data[1].operation is gate
        assert gate.label == "receiver-visible"
        assert out["old"] is old and out["new"] is metadata_owner(gate).metadata is not old
        assert qc._data[0].label is None
        assert qc._data[0].is_standard_gate() is (profile != "controlled-python")
        print(
            json.dumps(
                {"profile": profile, "round_trip": True, "exported_nodes": len(outgoing["nodes"])}
            )
        )
        return
    incoming = json.load(sys.stdin)
    public = CXGate() if profile == "controlled-python" else XGate()
    prepared = arena.prepare(incoming, sequence=1)
    assert public.label is None and "probe" not in metadata_owner(public).metadata
    qc = arena.commit(prepared)["qc"]
    gate = qc.data[0].operation
    assert gate is qc.data[1].operation
    assert (gate is public) is (profile != "clone")
    assert gate.label == "sender-visible"
    assert metadata_owner(gate).metadata["probe"] == profile
    assert qc._data[0].label is None
    assert qc._data[0].is_standard_gate() is (profile != "controlled-python")
    if profile == "clone":
        assert public.label is None
        assert gate.params is public.params and gate._definition is public._definition
    old = metadata_owner(gate).metadata
    metadata_owner(gate).metadata = dict(old)
    vars(gate)["_label"] = "receiver-visible"
    roots = {"qc": qc, "old": old, "new": metadata_owner(gate).metadata}
    print(json.dumps(arena.snapshot(roots, sequence=1)))


def main():
    command = [sys.executable, "-B", str(Path(__file__).resolve())]
    checks = []
    for profile in ("factory", "clone", "controlled-python"):
        with subprocess.Popen(
            command + ["origin", profile],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as origin:
            try:
                wire = origin.stdout.readline()
                assert json.loads(wire)["format"] == "call_graph_anchors_v1"
                remote = subprocess.run(
                    command + ["remote", profile],
                    input=wire,
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                assert remote.returncode == 0, remote.stderr
                stdout, stderr = origin.communicate(remote.stdout, timeout=45)
                assert origin.returncode == 0, stderr
                checks.append(json.loads(stdout))
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
                "scope": "trusted_circuit_only_singleton_wrappers",
                "production_bridge_integrated": False,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "system": platform.system(),
                "checks": checks,
                "source_sha256": {
                    name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in names
                },
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) == 3:
        peer(sys.argv[1], sys.argv[2])
    else:
        main()

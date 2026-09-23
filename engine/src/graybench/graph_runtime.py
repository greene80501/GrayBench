"""Explicit source files staged for the protected graph runtime."""

import shutil
from pathlib import Path

GRAPH_FILES = (
    "graph_wire.py",
    "graph_limits.py",
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
    "graph_control_flow.py",
    "graph_classical.py",
    "graph_loops.py",
    "graph_object_arrays.py",
    "graph_expressions.py",
    "symbolic_wire.py",
    "primitive_wire.py",
    "graph_rpc.py",
)


def stage_graph(directory):
    package = Path(directory) / "graybench"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name in GRAPH_FILES:
        shutil.copyfile(Path(__file__).with_name(name), package / name)

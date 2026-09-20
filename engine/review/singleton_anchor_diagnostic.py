"""Capture only the fixed public SDK singleton closure before user code executes."""

import hashlib
import json
import platform
from collections import Counter, deque
from pathlib import Path

import qiskit
from qiskit.circuit.library import get_standard_gate_name_mapping

import graybench.graph_wire as graph_module
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_types import SCALAR_MISSING, codec_for, scalar_record
from graybench.graph_wire import wire_bytes


def capture():
    factories = {
        name: value
        for name, value in sorted(get_standard_gate_name_mapping().items())
        if not value.mutable
    }
    singleton_names = {id(value): name for name, value in reversed(list(factories.items()))}
    identities, objects, records, pending = {}, {}, {}, deque()

    def ref(value):
        scalar = scalar_record(value)
        if scalar is not SCALAR_MISSING:
            return scalar
        if id(value) in identities:
            return {"ref": identities[id(value)]}
        handle = str(len(objects))
        identities[id(value)] = handle
        objects[handle] = value
        pending.append(handle)
        return {"ref": handle}

    roots = {name: ref(value) for name, value in factories.items()}
    while pending:
        if len(objects) > 10000:
            raise AssertionError("Public singleton closure exceeded audit bound")
        handle = pending.popleft()
        value = objects[handle]
        if id(value) in singleton_names:
            kind = "public_singleton"
            state = {"factory": singleton_names[id(value)], "attributes": ref(vars(value))}
        else:
            codec = codec_for(value)
            kind = codec.kind
            state = codec.state(value, ref)
        records[handle] = {"kind": kind, "state": state}
    return factories, objects, {"roots": roots, "records": records}


def main():
    factories, objects, graph = capture()
    registry = PublicAnchorRegistry.capture()
    registry.validate_manifest(registry.manifest())
    assert registry.snapshot() == graph
    for key, value in objects.items():
        assert registry.key_for(value) == key
        assert registry.resolve(key, kind=graph["records"][key]["kind"]) is value
    private = registry.private_copy()
    private_ids = {id(value): key for key, value in private.items()}

    def private_ref(value):
        scalar = scalar_record(value)
        return {"ref": private_ids[id(value)]} if scalar is SCALAR_MISSING else scalar

    for key, record in graph["records"].items():
        value = private[key]
        assert value is not objects[key] and type(value) is type(objects[key])
        state = (
            {"factory": record["state"]["factory"], "attributes": private_ref(vars(value))}
            if record["kind"] == "public_singleton"
            else codec_for(value).state(value, private_ref)
        )
        assert wire_bytes(state) == wire_bytes(record["state"])
    private_x = private[registry.key_for(factories["x"])]
    vars(private_x)["_label"] = "private copy"
    list.append(private_x.params, 123)
    private_x._definition.metadata["private-copy"] = True
    assert factories["x"].label is None and not factories["x"].params
    assert "private-copy" not in factories["x"]._definition.metadata
    first = wire_bytes(graph)
    again_factories, again_objects, again_graph = capture()
    assert wire_bytes(again_graph) == first
    assert set(objects) == set(again_objects)
    assert all(objects[key] is again_objects[key] for key in objects)
    assert all(factories[key] is again_factories[key] for key in factories)
    # A registry must retain original identities, not recapture/intern by value.
    original_metadata = factories["x"]._definition.metadata
    identity_set = {id(value) for value in objects.values()}
    try:
        replacement = dict(original_metadata)
        factories["x"]._definition.metadata = replacement
        assert replacement == original_metadata and replacement is not original_metadata
        assert id(original_metadata) in identity_set and id(replacement) not in identity_set
    finally:
        factories["x"]._definition.metadata = original_metadata
    names = (
        "graph_wire.py",
        "graph_anchors.py",
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
        "graph_singleton.py",
        "graph_anchor_bindings.py",
        "graph_python_ops.py",
        "graph_object_arrays.py",
        "graph_expressions.py",
        "symbolic_wire.py",
        "primitive_wire.py",
    )
    source_root = Path(graph_module.__file__).parent
    print(
        json.dumps(
            {
                "scope": "trusted_public_singleton_anchor_capture",
                "production_bridge_integrated": False,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "system": platform.system(),
                "factory_names": list(factories),
                "objects": len(objects),
                "graph_bytes": len(first),
                "kinds": dict(Counter(r["kind"] for r in graph["records"].values())),
                "graph_sha256": hashlib.sha256(first).hexdigest(),
                "same_process_repeat_identity": True,
                "runtime_registry_matches_independent_capture": True,
                "private_copy_exact_state_and_disjoint_identities": True,
                "private_mutation_isolated": True,
                "equal_replacement_is_not_a_baseline_anchor": True,
                "source_sha256": {
                    name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                    for name in names
                },
                "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

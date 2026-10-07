"""Probe trusted canonical evolution values through real local graph transfer.

This never executes model-generated code or qualifies an isolated runtime.
"""

import argparse
import ast
import hashlib
import importlib.util
import json
import platform
from pathlib import Path

import numpy as np
import qiskit
import scipy
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from graybench.circuit_wire import WireError
from graybench.datasets import load_suite
from graybench.gate_semantics import EVOLUTION_CHECK
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_delta import DeltaGraphArena
from graybench.graph_limits import GraphLimits
from graybench.graph_rpc import validate_root_shapes
from graybench.graph_wire import GraphArena
from graybench.matrix_semantics import CircuitMatrixJudge
from graybench.provenance import source_manifest

LIMITS = GraphLimits(depth=128, message_bytes=16 * 1024 * 1024)


def owner_chain(circuit):
    if not circuit.data or not circuit.data[0].operation.params:
        return []
    value = circuit.data[0].operation.params[0]
    if type(value) is not np.ndarray:
        return []
    result, seen = [], set()
    while value is not None:
        if id(value) in seen:
            raise ValueError("Cyclic array ownership")
        seen.add(id(value))
        record = {"type": type(value).__name__, "module": type(value).__module__}
        if type(value) is np.ndarray:
            record.update(
                shape=list(value.shape),
                strides=list(value.strides),
                dtype=value.dtype.str,
                owns_data=bool(value.flags.owndata),
                writeable=bool(value.flags.writeable),
            )
        else:
            try:
                view = memoryview(value)
            except TypeError:
                record["buffer_exported"] = False
            else:
                view.release()
                record["buffer_exported"] = True
        result.append(record)
        value = getattr(value, "base", None)
    return result


def numerical_outcome(circuit, label, time):
    if not isinstance(circuit, QuantumCircuit) or circuit.num_qubits != len(label):
        return "fail"
    basis = {
        "I": np.eye(2, dtype=complex),
        "X": np.array([[0, 1], [1, 0]], dtype=complex),
        "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
        "Z": np.array([[1, 0], [0, -1]], dtype=complex),
    }
    pauli = np.ones((1, 1), dtype=complex)
    for char in label:
        pauli = np.kron(pauli, basis[char])
    expected = np.cos(time) * np.eye(2 ** len(label)) - 1j * np.sin(time) * pauli
    actual = Operator(circuit).data
    valid = np.isfinite(actual).all() and np.allclose(actual, expected, atol=1e-10, rtol=0)
    return "pass" if valid else "fail"


def probe_case(implementation, label, time, limits=LIMITS):
    anchors = PublicAnchorRegistry.capture()
    sender = DeltaGraphArena(
        GraphArena(side="judge", session="canonical-probe", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    receiver = DeltaGraphArena(
        GraphArena(side="candidate", session="canonical-probe", limits=limits, anchors=anchors),
        wire_limit=limits.message_bytes,
    )
    request = sender.snapshot({"args": (label, time), "kwargs": {}}, sequence=1)
    incoming = receiver.commit(receiver.prepare(request, sequence=1))
    circuit = implementation(*incoming["args"])
    chain = owner_chain(circuit)
    record = {"label": label, "time": time, "owner_chain": chain}
    try:
        response = receiver.snapshot(
            {**incoming, "result": circuit, "exception_args": None}, sequence=1
        )
        prepared = sender.prepare(response, sequence=1)
        validate_root_shapes(prepared.snapshot, response=True, raised=None)
        reconstructed = sender.commit(prepared)["result"]
    except WireError as exc:
        # Only this known unsupported representation is a diagnostic outcome.
        # Unexpected protocol/transaction failures must fail the probe.
        if str(exc) != "External array buffer requires a graph codec":
            raise
        record.update(
            graph_outcome="unsupported",
            graph_detail=str(exc),
            reconstructed_numerical_outcome=None,
        )
    else:
        record.update(
            graph_outcome="supported",
            graph_detail=None,
            reconstructed_numerical_outcome=numerical_outcome(reconstructed, label, time),
        )
    # Extract the action only after transfer: Operator can populate SDK caches.
    record["numerical_outcome"] = numerical_outcome(circuit, label, time)
    return record


def report(cache):
    fixture_path = Path(__file__).with_name("matrix_semantics_controls.py")
    spec = importlib.util.spec_from_file_location("canonical_control_fixture", fixture_path)
    fixtures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixtures)
    check_tree = ast.parse(EVOLUTION_CHECK)
    assignment = next(
        node
        for node in ast.walk(check_tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "cases" for target in node.targets)
    )
    inputs = ast.literal_eval(assignment.value)
    judge = CircuitMatrixJudge("qhe116-evolution-graph-v2", image="sha256:" + "a" * 64)
    cases, sources = [], {}
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[116]
        task = judge.revise(source)  # Reject changed source records before executing fixtures.
        payload, manifest = judge.configuration(task)
        limits = GraphLimits.from_record(payload["graph_limits"])
        probe = next(probe for probe in fixtures.probes(source) if probe.name == "canonical")
        code = task.public.prompt + probe.completion if suite == "normal" else probe.completion
        namespace = {}
        exec(compile(code, "<trusted-canonical-fixture>", "exec"), namespace)
        function = namespace[task.public.entry_point]
        sources[suite] = {
            "source_task_digest": source.digest,
            "revised_task_digest": task.digest,
            "public_contract_digest": manifest["public_contract_digest"],
            "authored_completion_sha256": hashlib.sha256(probe.completion.encode()).hexdigest(),
        }
        for label, time in inputs:
            cases.append({"suite": suite, **probe_case(function, label, time, limits)})
    return {
        "kind": "graybench_canonical_evolution_local_transport_v1",
        "scope": "Trusted canonical fixture; fresh local arena per case; no model or container",
        "engine_source_digest": source_manifest()["digest"],
        "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_source_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "qiskit": qiskit.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "graph_limits": LIMITS.record(),
        "sources": sources,
        "cases": cases,
        "canonical_cases_supported": all(
            case["numerical_outcome"] == "pass"
            and case["graph_outcome"] == "supported"
            and case["reconstructed_numerical_outcome"] == "pass"
            for case in cases
        ),
        "runtime_qualified": False,
        "publication_eligible": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-supported", action="store_true")
    args = parser.parse_args(argv)
    result = report(args.cache)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    if args.require_supported and not result["canonical_cases_supported"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Recreate fixed host controls/calibration; no sandbox or model execution."""

import argparse
import ast
import hashlib
import importlib.util
import json
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from graybench.datasets import PINS, load_suite
from graybench.identity import canonical
from graybench.provenance import source_manifest
from graybench.task11_revision import CHECK, SOURCE_RECORDS, revised_task


def sha(data):
    return hashlib.sha256(data).hexdigest()


def values(array):
    return [[float(z.real), float(z.imag)] for z in array]


def circuit_record(circuit):
    return {
        "width": circuit.num_qubits,
        "global_phase": float(circuit.global_phase),
        "registers": [
            (r.name, len(r), [circuit.find_bit(q).index for q in r]) for r in circuit.qregs
        ],
        "instructions": [
            {
                "name": item.operation.name,
                "wires": [circuit.find_bit(q).index for q in item.qubits],
                "params": [float(p) for p in item.operation.params],
                "supplied_definition": circuit_record(item.operation.definition)
                if item.operation.name == "supplied"
                else None,
            }
            for item in circuit.data
        ],
    }


def build(cache):
    controls_path = Path(__file__).with_name("task11_controls.py")
    spec = importlib.util.spec_from_file_location("task11_fixed_controls", controls_path)
    controls = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controls)
    scope = {}
    exec(compile(CHECK, "authored-task11-check", "exec"), scope)
    calibrations = []
    for index, (circuit, matrix) in enumerate(scope["statevector_cases"]()):
        expected = matrix[:, 0]
        actual = Statevector.from_instruction(circuit).data
        error = float(np.max(np.abs(expected - actual)))
        if error >= 1e-14:
            raise ValueError("Independent state calibration failed")
        calibrations.append(
            {
                "case": index,
                "circuit": circuit_record(circuit),
                "independent_state": values(expected),
                "sdk_state": values(actual),
                "max_entry_error": error,
            }
        )
    observations = []
    original = []
    sources = []
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[11]
        if source.digest != SOURCE_RECORDS[suite]["digest"]:
            raise ValueError("Exact pinned Task 11 required before host execution")
        sources.append(
            {
                "suite": suite,
                "task_digest": source.digest,
                "public_digest": source.public.digest,
                "test_sha256": sha(source.upstream_test.encode()),
            }
        )
        task = revised_task(source)
        for probe in controls.probes(source):
            namespace = {}
            program = (
                task.public.prompt + probe.completion if suite == "normal" else probe.completion
            )
            exec(compile(program, "fixed-authored-task11-control", "exec"), namespace)
            implementation = namespace[task.public.entry_point]
            try:
                scope["check"](implementation)
            except AssertionError as exc:
                outcome, detail = "fail", str(exc)
            else:
                outcome, detail = "pass", None
            if outcome != probe.expectation:
                raise ValueError(f"Unexpected fixed control outcome: {suite}/{probe.name}")
            observations.append(
                {
                    "suite": suite,
                    "name": probe.name,
                    "expectation": probe.expectation,
                    "outcome": outcome,
                    "detail": detail,
                    "completion_sha256": sha(probe.completion.encode()),
                }
            )
            if probe.name == "fixed-upstream-example":
                nodes = [
                    node
                    for node in ast.parse(source.upstream_test).body
                    if isinstance(node, ast.FunctionDef) and node.name == "check"
                ]
                if len(nodes) != 1:
                    raise ValueError("Pinned check shape changed")
                upstream = {"QuantumCircuit": QuantumCircuit, "Statevector": Statevector}
                exec(
                    compile(
                        ast.Module(body=nodes, type_ignores=[]), "exact-pinned-task11-check", "exec"
                    ),
                    upstream,
                )
                upstream["check"](implementation)
                test = QuantumCircuit(2)
                test.x(0)
                wrong = implementation(test)
                # The X0 input has independently known basis state index one.
                expected = np.array([0, 1, 0, 0], dtype=complex)
                overlap = np.vdot(expected, wrong.data)
                aligned = wrong.data * np.exp(-1j * np.angle(overlap))
                error = float(np.max(np.abs(aligned - expected)))
                if error <= 1e-10:
                    raise ValueError("Fixed-state counterexample was not reproduced")
                original.append(
                    {
                        "suite": suite,
                        "name": probe.name,
                        "upstream_outcome": "pass",
                        "different_input": {"width": 2, "operations": [["x", [0]]]},
                        "expected_state": values(expected),
                        "returned_state": values(wrong.data),
                        "phase_aligned_max_entry_error": error,
                    }
                )
    return {
        "kind": "graybench_task11_host_verification_v1",
        "scope": (
            "fixed authored host controls and literal state calibration; no sandbox qualification"
        ),
        "publication_eligible": False,
        "independent_review": False,
        "engine_source": source_manifest(),
        "pins": PINS,
        "source_records": sources,
        "script_sha256": sha(Path(__file__).read_bytes()),
        "control_script_sha256": sha(controls_path.read_bytes()),
        "oracle_sha256": sha(CHECK.encode()),
        "environment": {
            "python": platform.python_version(),
            "qiskit": version("qiskit"),
            "numpy": version("numpy"),
        },
        "upstream_fixed_state_screen": original,
        "state_calibration": calibrations,
        "authored_controls": observations,
    }


def verify(report, cache):
    if canonical(report) != canonical(build(cache)):
        raise ValueError("Saved Task 11 verification differs from exact recreation")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build(args.cache)
    if args.check:
        verify(json.loads(args.output.read_bytes()), args.cache)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "calibrated_states": len(result["state_calibration"]),
                "controls": len(result["authored_controls"]),
                "publication_eligible": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

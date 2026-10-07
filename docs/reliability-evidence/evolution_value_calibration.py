"""Trusted authored evolution controls and independent finite oracle calibration.

Local subprocesses here are not sandboxed. Only hash-pinned authored fixtures
are executed; model-generated code must use the isolated production runner.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from itertools import product
from pathlib import Path

import numpy as np
import qiskit

from graybench.datasets import load_suite
from graybench.evolution_value import check_evolution_matrix
from graybench.protected_oracle_review import protected_probes
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import (
    WORKER,
    ValueExecution,
    parse_value_response,
    value_payload,
)
from graybench.provenance import source_manifest


def sha(data):
    return hashlib.sha256(data).hexdigest()


class TrustedFixtureRunner:
    def manifest(self, contract):
        return {
            "scope": "trusted authored controls in local subprocesses; no sandbox qualification",
            "worker_sha256": sha(WORKER.read_bytes()),
            "fixture_runner_sha256": sha(Path(__file__).read_bytes()),
            "contract_digest": contract.digest,
        }

    def execute(self, contract, completion, calls):
        wire = json.dumps(
            value_payload(contract, completion, calls), separators=(",", ":")
        ).encode()
        execution = subprocess.run(
            [sys.executable, str(WORKER)], input=wire, capture_output=True, timeout=30, check=False
        )
        if execution.returncode != 0:
            raise ValueError("Authored fixture worker failed to produce a response")
        if len(execution.stdout) >= 1024 * 1024:
            raise ValueError("Authored fixture exceeded the default output allowance")
        evidence = {
            "scope": "trusted authored local fixture",
            "payload_sha256": sha(wire),
            "response_sha256": sha(execution.stdout),
            "response_bytes": len(execution.stdout),
        }
        try:
            values = parse_value_response(execution.stdout, contract, expected_count=len(calls))
        except ValueError as exc:
            return ValueExecution("candidate_error", (), {**evidence, "parser_detail": str(exc)})
        return ValueExecution("returned", values, evidence)


def tensor_calibration():
    basis = {
        "I": np.eye(2, dtype=complex),
        "X": np.array([[0, 1], [1, 0]], dtype=complex),
        "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
        "Z": np.array([[1, 0], [0, -1]], dtype=complex),
    }
    count, maximum = 0, 0.0
    for width in range(1, 6):
        for letters in product("IXYZ", repeat=width):
            pauli = np.ones((1, 1), dtype=complex)
            for char in letters:
                pauli = np.kron(pauli, basis[char])
            for time in (0.0, -0.23, 0.71):
                matrix = np.cos(time) * np.eye(len(pauli)) - 1j * np.sin(time) * pauli
                value = [[[float(z.real), float(z.imag)] for z in row] for row in matrix]
                result = check_evolution_matrix("".join(letters), time, value)
                if not result["passed"]:
                    raise ValueError("Basis-index oracle disagrees with literal tensor calibration")
                maximum = max(maximum, result["max_entry_error"])
                count += 1
    return {
        "cases": count,
        "widths": [1, 2, 3, 4, 5],
        "times": [0.0, -0.23, 0.71],
        "maximum_entry_error": maximum,
        "phase_alignment": False,
    }


def report(cache):
    judge = ProtectedSemanticJudge(TrustedFixtureRunner())
    manifests, trials = {}, []
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[116]
        task = revised_value_task(source)
        manifests[suite] = judge.manifest(task)
        for probe in protected_probes(source):
            result = judge.evaluate(task, source, probe.completion)
            if result.outcome != probe.expectation:
                raise ValueError(
                    "Authored control differs from its frozen expectation: " + probe.name
                )
            trials.append(
                {
                    "suite": suite,
                    "control": probe.name,
                    "expected": probe.expectation,
                    "outcome": result.outcome,
                    "completion_sha256": sha(probe.completion.encode()),
                    "execution": result.evidence["candidate_execution"],
                    "case_results": result.evidence.get("case_results"),
                }
            )
    return {
        "kind": "graybench_evolution_matrix_value_local_calibration_v1",
        "scope": "Trusted authored algorithms and local worker/parser; no model or container",
        "engine_source_digest": source_manifest()["digest"],
        "calibration_source_sha256": sha(Path(__file__).read_bytes()),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "numpy": np.__version__,
            "qiskit": qiskit.__version__,
            "scipy": version("scipy"),
        },
        "manifests": manifests,
        "trials": trials,
        "tensor_calibration": tensor_calibration(),
        "publication_eligible": False,
        "independent_admission": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = report(args.cache)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(result, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
        )


if __name__ == "__main__":
    main()

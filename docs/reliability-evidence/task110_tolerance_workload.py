"""Deterministic pinned-image diagnostic of task 110's loose equivalence tolerance."""

import hashlib
import json
from pathlib import Path

import qiskit
from qiskit.quantum_info import Clifford, Operator, random_clifford

IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
REFERENCE_SEED = 1
CANDIDATE_SEEDS = tuple(range(2, 102))


def report() -> dict:
    reference = random_clifford(5, seed=REFERENCE_SEED).to_circuit()
    reference_clifford = Clifford(reference)
    reference_operator = Operator(reference)
    cases = []
    for seed in CANDIDATE_SEEDS:
        other = random_clifford(5, seed=seed).to_circuit()
        other_operator = Operator(other)
        cases.append(
            {
                "candidate_seed": seed,
                "same_clifford": bool(reference_clifford == Clifford(other)),
                "strict_operator_equiv": bool(
                    reference_operator.equiv(other_operator, rtol=0.0, atol=1e-9)
                ),
                "pinned_test_operator_equiv": bool(
                    reference_operator.equiv(other_operator, rtol=0.4, atol=0.4)
                ),
            }
        )
    return {
        "kind": "graybench_task110_tolerance_probe_v1",
        "scope": "deterministic local oracle diagnostic; not model scoring",
        "image": IMAGE,
        "qiskit_version": qiskit.__version__,
        "workload_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_seed": REFERENCE_SEED,
        "qubits": 5,
        "cases": cases,
        "counts": {
            "same_clifford": sum(case["same_clifford"] for case in cases),
            "strict_operator_equiv": sum(case["strict_operator_equiv"] for case in cases),
            "pinned_test_operator_equiv": sum(case["pinned_test_operator_equiv"] for case in cases),
        },
    }


if __name__ == "__main__":
    print(json.dumps(report(), sort_keys=True, separators=(",", ":")))

"""Reproduce task 2's pinned native oracle behavior with authored safe values.

This executes the pinned test on this host, not the protected GrayBench judge.
It never generates a model answer or modifies the dataset.
"""

import argparse
import hashlib
import json
import platform
from math import sqrt
from pathlib import Path

import qiskit
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from graybench.datasets import PINS, load_suite


def authored_cases():
    target = (Statevector.from_label("00") + Statevector.from_label("11")) / sqrt(2)

    class ClaimedState:
        def equiv(self, _other):
            return True

    class ForgedStatevector(Statevector):
        def equiv(self, _other, rtol=None, atol=None):
            return True

    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    return (
        ("canonical-vector", target, True),
        ("circuit-derived-vector", Statevector.from_instruction(circuit), True),
        ("global-phase-vector", 1j * target, True),
        ("phi-minus-vector", Statevector([1 / sqrt(2), 0, 0, -1 / sqrt(2)]), False),
        ("product-vector", Statevector.from_label("00"), False),
        ("claimed-equiv-object", ClaimedState(), False),
        ("forged-equiv-subclass", ForgedStatevector(Statevector.from_label("01").data), False),
    )


def exact_native_check(task, value):
    namespace = {
        "Statevector": Statevector,
        "sqrt": sqrt,
        task.public.entry_point: lambda: value,
    }
    try:
        exec(compile(task.upstream_test, "pinned_task2_test", "exec"), namespace)
        if task.public.suite == "normal":
            namespace["check"](namespace[task.public.entry_point])
    except Exception as exc:
        return False, type(exc).__name__
    return True, None


def probe(cache):
    rows = []
    task_records = {}
    for suite in ("normal", "hard"):
        task = load_suite(suite, cache)[2]
        if task.public.task_id != "qiskitHumanEval/2":
            raise ValueError("Pinned task 2 is missing")
        task_records[suite] = {
            "public_digest": task.public.digest,
            "judge_record_digest": task.digest,
            "upstream_test_sha256": hashlib.sha256(task.upstream_test.encode()).hexdigest(),
        }
        target = (Statevector.from_label("00") + Statevector.from_label("11")) / sqrt(2)
        for name, value, expected_valid in authored_cases():
            accepted, exception = exact_native_check(task, value)
            physical_equiv = isinstance(value, Statevector) and Statevector(value.data).equiv(
                target
            )
            rows.append(
                {
                    "suite": suite,
                    "case": name,
                    "returned_type": type(value).__name__,
                    "expected_valid": expected_valid,
                    "physical_equiv_after_trusted_rewrap": bool(physical_equiv),
                    "native_upstream_accept": accepted,
                    "exception_type": exception,
                }
            )
    return {
        "kind": "qhe_task2_native_oracle_probe_v1",
        "purpose": "Oracle review, not protected-judge validation or model scoring",
        "python": platform.python_version(),
        "qiskit": qiskit.__version__,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dataset_pins": PINS,
        "tasks": task_records,
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = probe(args.cache)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    expected = {
        (suite, case)
        for suite in ("normal", "hard")
        for case in ("claimed-equiv-object", "forged-equiv-subclass")
    }
    observed = {
        (row["suite"], row["case"])
        for row in record["cases"]
        if not row["expected_valid"] and row["native_upstream_accept"]
    }
    if observed != expected:
        raise SystemExit(f"Unexpected native false-accept set: {sorted(observed)}")
    print(f"verified {len(record['cases'])} native cases; {len(observed)} false accepts")


if __name__ == "__main__":
    main()

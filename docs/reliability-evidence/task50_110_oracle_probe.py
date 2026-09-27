"""Pinned task-50/110 diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from graybench.upstream import UpstreamJudge

FIRST_GATE_BODY = "\n    copied = circuit.copy()\n    del copied.data[0]\n    return copied\n"
UNCHANGED_BODY = "\n    return circuit.copy()\n"
EMPTY_BODY = "\n    return []\n"
COPIES_BODY = "\n    return [circuit.copy() for _ in range(n)]\n"
NONCLIFFORD_BODY = (
    "\n    from qiskit import QuantumCircuit\n"
    "    wrong = QuantumCircuit(circuit.num_qubits)\n"
    "    wrong.t(0)\n"
    "    return [wrong]\n"
)


def variants(task):
    if task.public.task_id.endswith("/50"):
        prefix = (
            ""
            if task.public.suite == "normal"
            else "def remove_gate_in_position(circuit, position):"
        )
        return {
            "reference": task.canonical_solution,
            "first_gate_only": prefix + FIRST_GATE_BODY,
            "unchanged_control": prefix + UNCHANGED_BODY,
        }
    prefix = "" if task.public.suite == "normal" else "def equivalent_clifford_circuit(circuit, n):"
    return {
        "empty_list": prefix + EMPTY_BODY,
        "equivalent_copies": prefix + COPIES_BODY,
        "nonclifford_control": prefix + NONCLIFFORD_BODY,
    }


def native_reference(task):
    source = (
        task.public.prompt + task.canonical_solution
        if task.public.suite == "normal"
        else task.canonical_solution
    )
    namespace = {}
    exec(compile(source, "<pinned-task50-reference>", "exec"), namespace)
    exec(compile(task.upstream_test, "<pinned-task50-test>", "exec"), namespace)
    if task.public.suite == "normal":
        namespace["check"](namespace[task.public.entry_point])
    return "pass"


def position_witness(task):
    namespace = {}
    exec(
        compile(task.public.prompt + FIRST_GATE_BODY, "<authored-position-witness>", "exec"),
        namespace,
    )
    circuit = qiskit.QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.h(1)
    circuit.h(0)
    expected = circuit.copy()
    del expected.data[1]
    actual = namespace["remove_gate_in_position"](circuit, 1)
    if actual == expected:
        raise RuntimeError("Position-one witness no longer distinguishes the mutant")
    return {
        "requested_position": 1,
        "output_equals_expected": actual == expected,
        "actual_first_gate": actual.data[0].operation.name,
        "expected_first_gate": expected.data[0].operation.name,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        50: {"reference": "unsupported", "first_gate_only": "pass", "unchanged_control": "fail"},
        110: {"empty_list": "pass", "equivalent_copies": "pass", "nonclifford_control": "fail"},
    }
    judge = UpstreamJudge(image=args.image)
    observations, native = [], []
    normal_50 = None
    for suite in ("normal", "hard"):
        tasks = {t.public.task_id: t for t in load_suite(suite, args.cache)}
        for number in (50, 110):
            task = tasks[f"qiskitHumanEval/{number}"]
            if number == 50:
                native.append(
                    {"suite": suite, "task_digest": task.digest, "outcome": native_reference(task)}
                )
                if suite == "normal":
                    normal_50 = task
            for name, code in variants(task).items():
                result = judge.evaluate(task, code)
                if result.outcome != expected[number][name]:
                    raise RuntimeError(f"Unexpected {suite}/{number}/{name}: {result.outcome}")
                observations.append(
                    {
                        "suite": suite,
                        "task_digest": task.digest,
                        "case": name,
                        "completion_sha256": hashlib.sha256(code.encode()).hexdigest(),
                        "outcome": result.outcome,
                        "judge_digest": result.judge_digest,
                    }
                )
    print(
        json.dumps(
            {
                "kind": "graybench_task50_110_oracle_probe_v1",
                "scope": "Pinned protected/native diagnostic, not a model score",
                "image": args.image,
                "host_python": platform.python_version(),
                "host_qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
                "native_task50_reference": native,
                "position_one_witness": position_witness(normal_50),
                "task110_requested_n": 10,
                "task110_empty_return_length": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

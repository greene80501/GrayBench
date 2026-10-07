"""Exact pinned task-148 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite
from qiskit.quantum_info import Operator
from qiskit_ibm_runtime.fake_provider import FakeKyiv

ROUTING_BODY = (
    "    from qiskit.transpiler.passes import BasicSwap\n"
    "    from qiskit.converters import circuit_to_dag, dag_to_circuit\n"
    "    mapped = dag_to_circuit(BasicSwap(backend.coupling_map).run(circuit_to_dag(qc)))\n"
)

AUTHORED = {
    "moved_single_qubit_gate": (
        ROUTING_BODY
        + "    for position, instruction in enumerate(mapped.data):\n"
        + "        if instruction.operation.num_qubits == 1:\n"
        + "            old = mapped.find_bit(instruction.qubits[0]).index\n"
        + "            new_qubit = mapped.qubits[(old + 1) % mapped.num_qubits]\n"
        + "            mapped.data[position] = instruction.replace(qubits=(new_qubit,))\n"
        + "            swap_map.mutations = getattr(swap_map, 'mutations', 0) + 1\n"
        + "            break\n"
        + "    return mapped\n"
    ),
    "extra_gate_control": ROUTING_BODY + "    mapped.x(0)\n    return mapped\n",
}


def cases(task):
    variants = {"reference": task.canonical_solution, **AUTHORED}
    for name, implementation in variants.items():
        if name == "reference":
            source = (
                task.public.prompt + implementation
                if task.public.suite == "normal"
                else implementation
            )
        elif task.public.suite == "normal":
            source = task.public.prompt + "\n" + implementation
        else:
            source = "def swap_map(qc, backend):\n" + implementation
        yield name, source


def fixed_input_witness(candidate):
    circuit = qiskit.QuantumCircuit(5)
    circuit.x(4)
    actual = candidate(circuit.copy(), FakeKyiv())
    return {
        "input_gate": "x on qubit 4",
        "operator_preserved": Operator(actual) == Operator(circuit),
        "output_gate_qubit": actual.find_bit(actual.data[0].qubits[0]).index,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "moved_single_qubit_gate": "pass",
        "extra_gate_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/148"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-148-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-148-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["swap_map"])
                outcome, detail = "pass", None
            except AssertionError as exc:
                outcome, detail = "fail", str(exc)
            except BaseException as exc:
                outcome, detail = "error", f"{type(exc).__name__}: {exc}"
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}; detail={detail}")
            candidate = namespace["swap_map"]
            observations.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "detail": detail,
                    "mutated_random_calls": getattr(candidate, "mutations", None),
                    "fixed_input_witness": (
                        fixed_input_witness(candidate) if outcome == "pass" else None
                    ),
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task148_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": observations,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

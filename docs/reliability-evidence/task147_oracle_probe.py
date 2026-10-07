"""Exact pinned task-147 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite

AUTHORED = {
    "equivalent_decomposition": (
        "    qc.sdg(4)\n"
        "    qc.mcx([0, 1, 2, 3], 4)\n"
        "    qc.s(4)\n"
        "    return qc\n"
    ),
    "fixed_prebuilt": (
        "    fixed = QuantumCircuit(6)\n"
        "    fixed.h([0, 4, 5])\n"
        "    fixed.append(YGate().control(4), range(5))\n"
        "    return fixed\n"
    ),
    "unchanged_control": "    return qc\n",
    "wrong_y_control": "    qc.y(4)\n    return qc\n",
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
            source = (
                "from qiskit import QuantumCircuit\n"
                "from qiskit.circuit.library import YGate\n\n"
                "def mcy(qc):\n" + implementation
            )
        yield name, source


def alternate_input_witness(candidate):
    alternate = qiskit.QuantumCircuit(6)
    alternate.x(5)
    expected = alternate.copy()
    expected.append(qiskit.circuit.library.YGate().control(4), range(5))
    actual = candidate(alternate.copy())
    return {
        "input_gate": "x on qubit 5",
        "expected_input_preserved": (
            qiskit.quantum_info.Operator(actual)
            == qiskit.quantum_info.Operator(expected)
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "equivalent_decomposition": "pass",
        "fixed_prebuilt": "pass",
        "unchanged_control": "fail",
        "wrong_y_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/147"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-147-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-147-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["mcy"])
                outcome, detail = "pass", None
            except AssertionError as exc:
                outcome, detail = "fail", str(exc)
            except BaseException as exc:
                outcome, detail = "error", f"{type(exc).__name__}: {exc}"
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}; detail={detail}")
            observations.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "detail": detail,
                    "alternate_input_witness": (
                        alternate_input_witness(namespace["mcy"])
                        if outcome == "pass"
                        else None
                    ),
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task147_exact_oracle_probe_v1",
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

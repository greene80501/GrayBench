"""Exact pinned task-139 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite

AUTHORED = {
    "empty_decomposition": "    return []\n",
    "fabricated_term": (
        "    from qiskit.quantum_info import Statevector\n"
        "    zero = Statevector.from_label('00')\n"
        "    return [(1.0, zero, zero)]\n"
    ),
    "negative_coefficient_control": (
        "    from qiskit.quantum_info import Statevector\n"
        "    zero = Statevector.from_label('00')\n"
        "    return [(-1.0, zero, zero)]\n"
    ),
    "wrong_dimension_control": (
        "    from qiskit.quantum_info import Statevector\n"
        "    zero = Statevector.from_label('0')\n"
        "    return [(1.0, zero, zero)]\n"
    ),
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
            source = "def schmidt_test(data, qargs_B):\n" + implementation
        yield name, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "empty_decomposition": "pass",
        "fabricated_term": "pass",
        "negative_coefficient_control": "fail",
        "wrong_dimension_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/139"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-139-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-139-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["schmidt_test"])
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
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task139_exact_oracle_probe_v1",
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

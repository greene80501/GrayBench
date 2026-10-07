"""Exact pinned tasks 142/143 diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite

VARIANTS = {
    142: {
        "valid_one_qubit": "    return [DensityMatrix.from_label('0') for _ in range(10)]\n",
        "wrong_two_qubit": "    return [DensityMatrix.from_label('00') for _ in range(10)]\n",
        "boundary_mixed": (
            "    return [DensityMatrix(np.eye(2) / 2) for _ in range(10)]\n"
        ),
        "low_purity_control": (
            "    return [DensityMatrix(np.eye(4) / 4) for _ in range(10)]\n"
        ),
        "wrong_length_control": (
            "    return [DensityMatrix.from_label('0') for _ in range(9)]\n"
        ),
    },
    143: {
        "valid_one_qubit": (
            "    zero = Statevector.from_label('0')\n"
            "    return [(zero, zero) for _ in range(10)]\n"
        ),
        "wrong_two_qubit": (
            "    zero = Statevector.from_label('00')\n"
            "    return [(zero, zero) for _ in range(10)]\n"
        ),
        "orthogonal_control": (
            "    zero, one = Statevector.from_label('0'), Statevector.from_label('1')\n"
            "    return [(zero, one) for _ in range(10)]\n"
        ),
        "wrong_length_control": (
            "    zero = Statevector.from_label('0')\n"
            "    return [(zero, zero) for _ in range(9)]\n"
        ),
    },
}

EXPECTED = {
    "reference": "pass",
    "valid_one_qubit": "pass",
    "wrong_two_qubit": "pass",
    "boundary_mixed": "pass",
    "low_purity_control": "fail",
    "orthogonal_control": "fail",
    "wrong_length_control": "fail",
}

FUNCTIONS = {142: "purity_dataset", 143: "fidelity_dataset"}


def cases(task, number):
    variants = {"reference": task.canonical_solution, **VARIANTS[number]}
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
            imports = (
                "from qiskit.quantum_info import DensityMatrix\nimport numpy as np\n"
                if number == 142
                else "from qiskit.quantum_info import Statevector\n"
            )
            source = imports + f"\ndef {FUNCTIONS[number]}():\n" + implementation
        yield name, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    observations = []
    for number in (142, 143):
        for suite in ("normal", "hard"):
            task = next(
                t
                for t in load_suite(suite, args.cache)
                if t.public.task_id == f"qiskitHumanEval/{number}"
            )
            for name, source in cases(task, number):
                namespace = {}
                try:
                    exec(
                        compile(source, f"<authored-task-{number}-solution>", "exec"),
                        namespace,
                    )
                    exec(compile(task.upstream_test, "<pinned-test>", "exec"), namespace)
                    if suite == "normal":
                        namespace["check"](namespace[FUNCTIONS[number]])
                    outcome, detail = "pass", None
                except AssertionError as exc:
                    outcome, detail = "fail", str(exc)
                except BaseException as exc:
                    outcome, detail = "error", f"{type(exc).__name__}: {exc}"
                if outcome != EXPECTED[name]:
                    raise RuntimeError(
                        f"Unexpected task {number}/{suite}/{name}: {outcome}; detail={detail}"
                    )
                observations.append(
                    {
                        "task": number,
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
                "kind": "graybench_tasks142_143_exact_oracle_probe_v1",
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

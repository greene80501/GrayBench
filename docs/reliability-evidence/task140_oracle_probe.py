"""Exact pinned task-140 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite

AUTHORED = {
    "valid_uniform": "    return [[1 / 16] * 16 for _ in range(10)]\n",
    "invalid_total_mass": "    return [[0.1] * 16 for _ in range(10)]\n",
    "wrong_length_control": "    return [[0.1] * 15 for _ in range(10)]\n",
    "zero_entropy_control": "    return [[1] + [0] * 15 for _ in range(10)]\n",
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
            source = "def shannon_entropy_data(ε):\n" + implementation
        yield name, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "valid_uniform": "pass",
        "invalid_total_mass": "pass",
        "wrong_length_control": "fail",
        "zero_entropy_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/140"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-140-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-140-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["shannon_entropy_data"])
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
                "kind": "graybench_task140_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "invalid_total_mass": 1.6,
                "cases": observations,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

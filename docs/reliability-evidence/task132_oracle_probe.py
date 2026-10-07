"""Exact pinned task-132 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite

COUNTS = {"110": 423, "100": 474, "000": 58, "010": 52, "101": 8, "111": 8, "011": 1}


def authored_body(*, wrong_count=False, wrong_container=False):
    result = "(first, second)" if wrong_container else "[first, second]"
    mutation = "    first['110'] += 1\n" if wrong_count else ""
    return (
        f"    counts = {COUNTS!r}\n"
        "    first, second = counts.copy(), counts.copy()\n"
        + mutation
        + f"    return {result}\n"
    )


def cases(task):
    variants = {
        "reference": task.canonical_solution,
        "fabricated_counts": authored_body(),
        "wrong_count_control": authored_body(wrong_count=True),
        "wrong_container_control": authored_body(wrong_container=True),
    }
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
            source = "def run_batched_random_circuits():\n" + implementation
        yield name, source, implementation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "fabricated_counts": "pass",
        "wrong_count_control": "fail",
        "wrong_container_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/132"
        )
        for name, source, implementation in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-132-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-132-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["run_batched_random_circuits"])
                outcome, detail = "pass", None
            except AssertionError as exc:
                outcome, detail = "fail", str(exc)
            except BaseException as exc:
                outcome, detail = "error", f"{type(exc).__name__}: {exc}"
            if name in expected and outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}; detail={detail}")
            if name == "fabricated_counts":
                assert "Batch" not in implementation and "Sampler" not in implementation
            observations.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "detail": detail,
                    "uses_batch_or_sampler": (
                        "Batch" in implementation or "Sampler" in implementation
                    ),
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task132_exact_oracle_probe_v1",
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

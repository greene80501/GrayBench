"""Exact pinned task-115 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
import re
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite


def change_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r}")
    return source.replace(old, new)


def candidates(reference):
    zero_errors, count = re.subn(r"error=0\.\d+", "error=0.0", reference)
    if count != 4:
        raise ValueError("Expected four reference errors")
    return {
        "reference": reference,
        "zero_errors": zero_errors,
        "wrong_parameter_names": change_once(
            reference, '("theta", "phi", "lambda")', '("x", "y", "z")'
        ),
        "constant_ugate": change_once(reference, "UGate(theta, phi, lam)", "UGate(0, 0, 0)"),
        "negative_error_control": change_once(reference, "error=0.00038115", "error=-0.1"),
        "zero_duration_control": change_once(reference, "duration=5.23e-8", "duration=0.0"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    cases = []
    expected = {
        "reference": "pass",
        "zero_errors": "pass",
        "wrong_parameter_names": "pass",
        "constant_ugate": "pass",
        "negative_error_control": "fail",
        "zero_duration_control": "fail",
    }
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/115"
        )
        for name, solution in candidates(task.canonical_solution).items():
            source = task.public.prompt + solution if suite == "normal" else solution
            namespace = {}
            try:
                exec(compile(source, "<authored-task-115-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-115-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["create_target"])
                outcome, error = "pass", None
            except AssertionError as exc:
                outcome, error = "fail", str(exc)
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}")
            cases.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "assertion": error,
                }
            )
    record = {
        "kind": "graybench_task115_exact_oracle_probe_v1",
        "scope": "Authored exact-test diagnostic, not protected judging or a model score",
        "image": args.image,
        "python": platform.python_version(),
        "qiskit": qiskit.__version__,
        "dataset_pins": PINS,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cases": cases,
    }
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

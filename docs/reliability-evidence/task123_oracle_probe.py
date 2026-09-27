"""Exact pinned task-123 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import matplotlib
import qiskit
from graybench.datasets import PINS, load_suite


def authored_body(*, axes=5, title="fake_belem Error Map"):
    return (
        "    from matplotlib.figure import Figure\n"
        "    figure = Figure()\n"
        f"    for index in range({axes}):\n"
        f"        figure.add_subplot({axes}, 1, index + 1)\n"
        f"    figure.suptitle({title!r})\n"
        "    return figure\n"
    )


def cases(task):
    variants = {
        "reference": task.canonical_solution,
        "blank_five_axes": authored_body(),
        "wrong_title_control": authored_body(title="wrong title"),
        "wrong_axis_count_control": authored_body(axes=4),
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
            source = "def backend_error_map():\n" + implementation
        yield name, source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "blank_five_axes": "pass",
        "wrong_title_control": "fail",
        "wrong_axis_count_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/123"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-123-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-123-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["backend_error_map"])
                outcome, assertion = "pass", None
            except AssertionError as exc:
                outcome, assertion = "fail", str(exc)
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}")
            figure = namespace["backend_error_map"]()
            if name != "reference" and any(axis.has_data() for axis in figure.axes):
                raise RuntimeError("Authored blank-figure fixture unexpectedly has plotted data")
            observations.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "assertion": assertion,
                    "axis_count": len(figure.axes),
                    "axes_with_data": sum(axis.has_data() for axis in figure.axes),
                    "suptitle": figure.get_suptitle(),
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task123_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "matplotlib": matplotlib.__version__,
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

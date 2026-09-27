"""Exact pinned task-150 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise RuntimeError(f"Expected one source occurrence: {before!r}")
    return source.replace(before, after)


def cases(task):
    reference = task.canonical_solution
    no_break = replace_once(reference, "qc.break_loop()", "qc.cx(0, 1)")
    wrong_condition = replace_once(
        reference,
        "with qc.if_test((qc.clbits[0], 1)):",
        "with qc.if_test((qc.clbits[0], 0)):",
    )
    fixed_two = replace_once(reference, "range(n)", "range(2)")
    fixed_two = replace_once(fixed_two, "pi/n*i", "pi/2*i")
    wrong_rotation = replace_once(
        reference, "qc.ry(pi/n*i, 0)", "qc.ry(pi/n*i + 0.1, 0)"
    )
    wrong_range = replace_once(reference, "range(n)", "range(n + 1)")
    variants = {
        "reference": reference,
        "no_break": no_break,
        "wrong_condition": wrong_condition,
        "fixed_two_iterations": fixed_two,
        "wrong_rotation_control": wrong_rotation,
        "wrong_range_control": wrong_range,
    }
    for name, implementation in variants.items():
        source = (
            task.public.prompt + implementation
            if task.public.suite == "normal"
            else implementation
        )
        yield name, source


def witness(candidate):
    circuit = candidate(qiskit.QuantumCircuit(2, 1), 3)
    loop = circuit.data[0].operation
    indexset, _, body = loop.params
    branch = body.data[4].operation
    return {
        "requested_iterations": 3,
        "loop_indexset": list(indexset),
        "if_condition_value": branch.condition[1],
        "if_body_operations": [item.operation.name for item in branch.blocks[0].data],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "no_break": "pass",
        "wrong_condition": "pass",
        "fixed_two_iterations": "pass",
        "wrong_rotation_control": "fail",
        "wrong_range_control": "fail",
    }
    observations = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/150"
        )
        for name, source in cases(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-150-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-150-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["for_loop_circuit"])
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
                    "n3_witness": (
                        witness(namespace["for_loop_circuit"])
                        if outcome == "pass"
                        else None
                    ),
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task150_exact_oracle_probe_v1",
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

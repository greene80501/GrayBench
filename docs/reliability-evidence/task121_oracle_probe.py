"""Exact pinned task-121 oracle diagnostic; never a model-scoring path."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import qiskit
from graybench.datasets import PINS, load_suite


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r}")
    return source.replace(old, new)


def candidates(reference):
    correction = "    with qc.if_test((cr[0], 1)):\n        qc.x(qr[0])\n"
    return {
        "reference": reference,
        "unconditional_reset": replace_once(
            reference,
            correction,
            "    with qc.if_test((cr[0], 1)):\n        qc.id(qr[0])\n    qc.reset(qr[0])\n",
        ),
        "no_first_measure": replace_once(
            replace_once(
                reference,
                "    qc.measure(qr[0], cr[0])\n",
                "    qc.barrier(qr[0])\n",
            ),
            correction,
            correction + "    qc.reset(qr[0])\n",
        ),
        "uncorrected_control": replace_once(
            reference,
            correction,
            "    with qc.if_test((cr[0], 1)):\n        qc.id(qr[0])\n",
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    expected = {
        "reference": "pass",
        "unconditional_reset": "pass",
        "no_first_measure": "pass",
        "uncorrected_control": "fail",
    }
    cases = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/121"
        )
        for name, solution in candidates(task.canonical_solution).items():
            source = task.public.prompt + solution if suite == "normal" else solution
            namespace = {}
            try:
                exec(compile(source, "<authored-task-121-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-121-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace["conditional_two_qubit_circuit"])
                outcome, assertion = "pass", None
            except AssertionError as exc:
                outcome, assertion = "fail", str(exc)
            if outcome != expected[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}")
            circuit = namespace["conditional_two_qubit_circuit"]()
            ops = dict(circuit.count_ops())
            if name == "unconditional_reset" and not (
                ops.get("reset") == 1 and ops.get("measure") == 2
            ):
                raise RuntimeError("Reset fixture did not retain both measurements")
            if name == "no_first_measure" and not (
                ops.get("reset") == 1 and ops.get("measure") == 1
            ):
                raise RuntimeError("Missing-measurement fixture was not built as intended")
            cases.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "outcome": outcome,
                    "assertion": assertion,
                    "ops": ops,
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task121_exact_oracle_probe_v1",
                "scope": "Authored exact-test diagnostic, not protected judging or a model score",
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cases": cases,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

"""Test whether pinned task 62 accepts a sender circuit that ignores both inputs.

Run from engine/ with a SHA-256-pinned local QHE cache. This writes append-only
native diagnostic evidence; it never scores a model or admits a task.
"""

import argparse
import hashlib
from pathlib import Path

from graybench.datasets import EXTERNAL_IDS, load_suite
from graybench.native_cohort import freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.reference_scan import run_evidence_cases


def fixed_answer(suite: str) -> str:
    body = "    qc = QuantumCircuit(5)\n    qc.x([1, 2, 3])\n    qc.h([0, 3])\n    return qc\n"
    if suite == "normal":
        return "\n" + body
    return "from qiskit import QuantumCircuit\ndef bb84_senders_circuit(state, basis):\n" + body


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    cases = []
    judges = {}
    cohorts = {}
    for suite in ("normal", "hard"):
        pinned = load_suite(suite, args.cache)
        task = next(task for task in pinned if task.public.task_id == "qiskitHumanEval/62")
        extraction = (
            "exact_prompt_suffix_v1" if suite == "normal" else "raw_or_single_python_fence_v1"
        )
        cohort = freeze_native_cohort(
            (task,),
            cache=args.cache,
            suite=suite,
            population="custom_development",
            image=args.image,
            extraction=extraction,
            label="task 62 fixed-input oracle diagnostic",
            excluded={
                task_key(other): (
                    "external_service"
                    if int(other.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
                    else "out_of_scope_development"
                )
                for other in pinned
                if other != task
            },
        )
        judges[suite] = NativeJudge(cohort, (task,), cache=args.cache)
        cohorts[suite] = cohort.digest
        cases.extend(
            [
                (f"{task_key(task)}/canonical", task.digest, (task, task.canonical_solution)),
                (
                    f"{task_key(task)}/fixed-input-ignoring",
                    task.digest,
                    (task, fixed_answer(suite)),
                ),
            ]
        )

    result = run_evidence_cases(
        cases,
        lambda case: judges[case[0].public.suite].evaluate(*case),
        args.output,
        purpose="native task-62 oracle counterexample; not model scoring or admission",
        selection={
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cohorts": cohorts,
            "image": args.image,
            "mutant": "fixed X(1,2,3), H(0,3) circuit ignores state and basis",
            "counterexample": (
                "state=[0,0,0,0,0], basis=[0,0,0,0,0] should prepare |00000>; mutant does not"
            ),
        },
    )
    print(result)


if __name__ == "__main__":
    main()

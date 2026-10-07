"""Source-bound native task-63 canonical and constant-answer controls.

Run from engine/ with PYTHONPATH=src and a pinned local dataset cache. This
creates a new evidence file; it does not generate model answers or alter scores.
"""

import argparse
import hashlib
from pathlib import Path

from graybench.datasets import load_suite
from graybench.native_cohort import freeze_native_cohort
from graybench.native_judge import NativeJudge
from graybench.reference_scan import run_evidence_cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()

    cases = []
    judges = {}
    cohorts = {}
    for suite in ("normal", "hard"):
        task = load_suite(suite, args.cache)[63]
        policy = "exact_prompt_suffix_v1" if suite == "normal" else "raw_or_single_python_fence_v1"
        cohort = freeze_native_cohort(
            (task,),
            cache=args.cache,
            suite=suite,
            population="custom_development",
            image=args.image,
            extraction=policy,
            label="task63 native control",
            excluded={
                f"{suite}/qiskitHumanEval/{number}": "out_of_scope_development"
                for number in range(151)
                if number != 63
            },
        )
        cohorts[suite] = {"digest": cohort.digest, "policy": policy}
        judges[suite] = NativeJudge(cohort, (task,), cache=args.cache, docker=args.docker)
        constant = (
            "\n    return '1'\n"
            if suite == "normal"
            else "def bb84_circuit_generate_key(senders_basis, circuit):\n    return '1'\n"
        )
        for label, completion in (("canonical", task.canonical_solution), ("constant", constant)):
            cases.append(
                (f"{suite}/{task.public.task_id}/{label}", task.digest, (task, completion))
            )

    result = run_evidence_cases(
        cases,
        lambda case: judges[case[0].public.suite].evaluate(*case),
        args.output,
        purpose="native task63 oracle control; not model scoring",
        selection={
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cohorts": cohorts,
            "image": args.image,
            "controls": "canonical and fixed-string-1",
        },
    )
    print(result)


if __name__ == "__main__":
    main()

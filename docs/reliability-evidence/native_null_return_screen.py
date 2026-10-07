"""Screen pinned offline native tests with a deliberately incomplete answer.

Run from engine/ with PYTHONPATH=src and a pinned local dataset cache. The
append-only output is diagnostic evidence, never a model score or task-admission
decision. A pass alone is suspicious only after the public contract is read:
some tasks may legitimately return None after mutating an input.
"""

import argparse
import hashlib
from pathlib import Path

from graybench.datasets import EXTERNAL_IDS, load_suite
from graybench.native_cohort import freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.reference_scan import run_evidence_cases


def null_answer(task) -> str:
    if task.public.suite == "normal":
        return "\n    return None\n"
    return f"def {task.public.entry_point}(*args, **kwargs):\n    return None\n"


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
        pinned = load_suite(suite, args.cache)
        tasks = tuple(
            task
            for task in pinned
            if int(task.public.task_id.rsplit("/", 1)[1]) not in EXTERNAL_IDS
        )
        policy = "exact_prompt_suffix_v1" if suite == "normal" else "raw_or_single_python_fence_v1"
        cohort = freeze_native_cohort(
            tasks,
            cache=args.cache,
            suite=suite,
            population="offline_143",
            image=args.image,
            extraction=policy,
            label="native null-return diagnostic",
            excluded={
                task_key(task): "external_service"
                for task in pinned
                if int(task.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
            },
        )
        cohorts[suite] = {"digest": cohort.digest, "policy": policy}
        judges[suite] = NativeJudge(cohort, tasks, cache=args.cache, docker=args.docker)
        cases.extend((task_key(task), task.digest, (task, null_answer(task))) for task in tasks)

    result = run_evidence_cases(
        cases,
        lambda case: judges[case[0].public.suite].evaluate(*case),
        args.output,
        purpose="native null-return screening; not model scoring or task admission",
        selection={
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cohorts": cohorts,
            "image": args.image,
            "mutant": "normal newline-indented return None; hard variadic function returning None",
        },
    )
    print(result)


if __name__ == "__main__":
    main()

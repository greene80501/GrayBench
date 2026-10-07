"""Screen every offline native task with a constant string-one answer.

Run from engine/ with PYTHONPATH=src and a pinned local dataset cache. This is
diagnostic evidence, never a model score or task-admission decision. A pass
requires review of the specific public contract before calling it a false pass.
"""

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from graybench.datasets import EXTERNAL_IDS, load_suite
from graybench.native_cohort import freeze_native_cohort, task_key
from graybench.native_judge import NativeJudge
from graybench.reference_scan import run_evidence_cases


def constant_one_answer(task) -> str:
    if task.public.suite == "normal":
        return '\n    return "1"\n'
    return f'def {task.public.entry_point}(*args, **kwargs):\n    return "1"\n'


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
        extraction = (
            "exact_prompt_suffix_v1" if suite == "normal" else "raw_or_single_python_fence_v1"
        )
        cohort = freeze_native_cohort(
            tasks,
            cache=args.cache,
            suite=suite,
            population="offline_143",
            image=args.image,
            extraction=extraction,
            exception_policy="test_exception_is_failure_v1",
            label="native constant-one diagnostic",
            excluded={
                task_key(task): "external_service"
                for task in pinned
                if int(task.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
            },
        )
        cohorts[suite] = {"digest": cohort.digest, "extraction": extraction}
        judges[suite] = NativeJudge(cohort, tasks, cache=args.cache, docker=args.docker)
        cases.extend(
            (task_key(task), task.digest, (task, constant_one_answer(task))) for task in tasks
        )

    result = run_evidence_cases(
        cases,
        lambda case: judges[case[0].public.suite].evaluate(*case),
        args.output,
        purpose="native constant-one oracle control; not model scoring or task admission",
        selection={
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cohorts": cohorts,
            "image": args.image,
            "exception_policy": "test_exception_is_failure_v1",
            "mutant": 'normal newline-indented return "1"; hard variadic function returning "1"',
        },
    )
    counts = Counter(result["results"].values())
    print(
        {
            "complete": result["complete"],
            "planned": result["planned"],
            "counts": dict(counts),
            "passes": sorted(
                key for key, outcome in result["results"].items() if outcome == "pass"
            ),
            "chain_head": result["chain_head"],
            "file_sha256": result["file_sha256"],
        }
    )


if __name__ == "__main__":
    main()

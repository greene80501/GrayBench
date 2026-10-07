"""Source-guarded repeat of task 63 canonical answers; never a model score."""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.reference_scan import run_evidence_cases
from graybench.upstream import UpstreamJudge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--repeats", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100:
        raise ValueError("Repeat count must be within 1..100")
    tasks = tuple(
        task
        for suite in ("normal", "hard")
        for task in load_suite(suite, args.cache)
        if task.public.family_id == "qhe/63"
    )
    if len(tasks) != 2:
        raise ValueError("Expected both pinned task-63 variants")
    items = [
        (
            f"{task.public.suite}/qiskitHumanEval/63/repeat-{number:02d}",
            identity(
                {"task": task.digest, "completion": task.canonical_solution, "repeat": number}
            ),
            task,
        )
        for task in tasks
        for number in range(1, args.repeats + 1)
    ]
    judge = UpstreamJudge(image=args.image, docker=args.docker, protocol=4)
    result = run_evidence_cases(
        items,
        lambda task: judge.evaluate(task, task.canonical_solution),
        args.output,
        purpose="task 63 stochastic canonical-reference diagnostic; not model scoring",
        selection={
            "family": 63,
            "suites": ["normal", "hard"],
            "repeats_per_suite": args.repeats,
            "image": args.image,
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    )
    counts = {
        suite: {
            outcome: sum(
                key.startswith(suite + "/") and verdict == outcome
                for key, verdict in result["results"].items()
            )
            for outcome in ("pass", "fail", "unsupported", "infrastructure_error", "timeout")
        }
        for suite in ("normal", "hard")
    }
    print(
        json.dumps(
            {
                "planned": result["planned"],
                "complete": result["complete"],
                "file_sha256": result["file_sha256"],
                "chain_head": result["chain_head"],
                "counts": counts,
            }
        )
    )


if __name__ == "__main__":
    main()

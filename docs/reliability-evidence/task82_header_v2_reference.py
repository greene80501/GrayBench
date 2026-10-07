"""Replay the exact pinned normal/hard task 82 references on file-semantic v2."""

import argparse
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.file_judge import QpyFileJudge
from graybench.reference_scan import run_reference_scan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--parser-image", required=True)
    args = parser.parse_args()
    tasks = tuple(
        task
        for suite in ("normal", "hard")
        for task in load_suite(suite, args.cache)
        if task.public.family_id == "qhe/82"
    )
    if len(tasks) != 2 or {task.public.suite for task in tasks} != {"normal", "hard"}:
        raise ValueError("Expected exactly one pinned task 82 in each suite")
    judge = QpyFileJudge(
        image=args.image, parser_image=args.parser_image, track="task82-file-semantic-v2"
    )
    result = run_reference_scan(
        tasks,
        judge,
        args.output,
        selection={
            "recipe": "task82-file-semantic-v2",
            "candidate_oracle_image": args.image,
            "parser_image": args.parser_image,
        },
    )
    print(json.dumps(result, sort_keys=True))
    if not result["complete"] or set(result["results"].values()) != {"pass"}:
        raise SystemExit("Reference control did not pass")


if __name__ == "__main__":
    main()

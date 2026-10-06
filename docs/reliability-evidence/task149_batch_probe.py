"""Freeze and run protected task-149 authored controls; never a model score.

From engine/, freeze the plan before Docker evaluation:
  uv run --locked --extra dataset python ../docs/reliability-evidence/task149_batch_probe.py
    PLAN.json --freeze-plan --cache CACHE --image sha256:...
Run only from the source checkout that produced that plan:
  uv run --locked --extra dataset python ../docs/reliability-evidence/task149_batch_probe.py
    CONTROLS.jsonl --plan PLAN.json --cache CACHE --image sha256:...
Both outputs are exclusive-create. An interrupted evidence log needs adjudication.
"""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.evaluation_recipes import recipe_judge
from graybench.identity import canonical, identity
from graybench.judge import Judgment
from graybench.reference_scan import run_evidence_cases
from graybench.task149_revision import PINNED_SOURCE_TASK_DIGESTS

RECIPE = "qhe149-most-common-bitstring-v1"
CONTROLS = (
    ("reference", None, "pass"),
    (
        "count-based",
        "    counts = bits.get_counts()\n    return max(counts, key=counts.get)\n",
        "pass",
    ),
    ("first-string", "    return bits.get_bitstrings()[0]\n", "fail"),
    ("last-string", "    return bits.get_bitstrings()[-1]\n", "fail"),
    ("fixed-string", "    return '001'\n", "fail"),
    ("wrong-type", "    return 1\n", "fail"),
    ("candidate-exception", "    raise RuntimeError('deliberate control')\n", "candidate_error"),
)


def completion(suite: str, body: str | None, original) -> str:
    if body is None:
        return original.canonical_solution
    if suite == "normal":
        return "\n" + body
    return "from qiskit.primitives import BitArray\n\ndef most_common_result(bits):\n" + body


def plan_cases(cache: Path, judge, *, image: str) -> tuple[list, dict]:
    originals = [
        next(task for task in load_suite(suite, cache) if task.public.family_id == "qhe/149")
        for suite in ("normal", "hard")
    ]
    if any(task.digest != PINNED_SOURCE_TASK_DIGESTS[task.public.suite] for task in originals):
        raise ValueError("Pinned task 149 source changed")
    cases = []
    selection = {}
    declared_judges = {}
    for original in originals:
        suite = original.public.suite
        revised = judge.revise(original)
        declared = judge.configuration(revised)[1]
        if declared["inner"]["image"] != image:
            raise ValueError("Declared task 149 judge image differs from requested image")
        declared_judges[f"{suite}/{original.public.task_id}"] = declared
        for name, body, expected in CONTROLS:
            code = completion(suite, body, original)
            key = f"{suite}/149/{name}"
            record = {
                "original_task_digest": original.digest,
                "revised_task_digest": revised.digest,
                "revised_public_digest": revised.public.digest,
                "completion_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "expected": expected,
            }
            selection[key] = record
            cases.append((key, identity(record), (revised, code, expected)))
    return cases, {
        "recipe": RECIPE,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "image": image,
        "cases": selection,
        "declared_judges": declared_judges,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze-plan", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()
    if args.freeze_plan == (args.plan is not None):
        parser.error("Choose exactly one of --freeze-plan or --plan")
    judge = recipe_judge(RECIPE, image=args.image, docker=args.docker)
    cases, selection = plan_cases(args.cache, judge, image=args.image)
    frozen = canonical(selection) + b"\n"
    if args.freeze_plan:
        with args.output.open("xb") as stream:
            stream.write(frozen)
        print(json.dumps({"plan_sha256": hashlib.sha256(frozen).hexdigest()}, sort_keys=True))
        return
    if args.plan.read_bytes() != frozen:
        raise ValueError("Frozen task 149 control plan differs from current source")

    def evaluate(case):
        revised, code, expected = case
        result = judge.evaluate(revised, code)
        key = f"{revised.public.suite}/{revised.public.task_id}"
        declared = selection["declared_judges"][key]
        if result.judge_digest != identity(declared) or result.evidence.get("manifest") != declared:
            raise ValueError("Observed task 149 judge differs from predeclared judge")
        return Judgment(
            result.outcome,
            result.judge_digest,
            {
                "expected": expected,
                "matches_expectation": result.outcome == expected,
                "judgment": result.evidence,
            },
        )

    summary = run_evidence_cases(
        cases,
        evaluate,
        args.output,
        purpose="Task 149 protected authored controls; not model scoring",
        selection=selection,
    )
    if not summary["complete"] or any(
        summary["results"][key] != record["expected"] for key, record in selection["cases"].items()
    ):
        raise AssertionError("Task 149 controls did not match predeclared outcomes")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

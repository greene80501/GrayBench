"""Predeclared protected BB84 batch controls; never a model score.

From engine/, freeze the plan before execution:
  uv run --locked --extra dataset python ../docs/reliability-evidence/task63_batch_probe.py
    PLAN.json --freeze-plan --cache CACHE --image sha256:...
Then run with the exact frozen plan:
  uv run --locked --extra dataset python ../docs/reliability-evidence/task63_batch_probe.py
    CONTROLS.jsonl --plan PLAN.json --cache CACHE --image sha256:...
Both outputs are exclusive-create. Interrupted evidence requires adjudication.
"""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.bb84_revision import HARD_REFERENCE, PINNED_SOURCE_TASK_DIGESTS, REFERENCE_BODY
from graybench.datasets import load_suite
from graybench.evaluation_recipes import recipe_judge
from graybench.identity import canonical, identity
from graybench.judge import Judgment
from graybench.reference_scan import run_evidence_cases
from task63_explicit_bases_probe import BASIS_ONLY, ERROR, FIXED, NO_SIFT, REVERSED, STATEVECTOR

RECIPE = "qhe63-explicit-bases-v2"
IN_PLACE_STATEVECTOR = """from qiskit.quantum_info import Statevector
def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    for i, basis in enumerate(receivers_basis):
        if basis:
            circuit.h(i)
    state = Statevector.from_instruction(circuit)
    return ''.join(str(int(state.probabilities([i])[1] > 0.5))
                   for i in range(len(senders_basis))
                   if senders_basis[i] == receivers_basis[i])
"""


def plan_cases(cache: Path, judge, *, image: str) -> tuple[list, dict]:
    originals = [
        next(task for task in load_suite(suite, cache) if task.public.family_id == "qhe/63")
        for suite in ("normal", "hard")
    ]
    if any(task.digest != PINNED_SOURCE_TASK_DIGESTS[task.public.suite] for task in originals):
        raise ValueError("Pinned task 63 source changed")
    cases = []
    selection = {}
    declared_judges = {}
    for original in originals:
        suite = original.public.suite
        revised = judge.revise(original)
        declared = judge.configuration(revised)[1]
        if declared["inner"]["image"] != image:
            raise ValueError("Predeclared BB84 judge image differs from requested image")
        declared_judges[f"{suite}/{original.public.task_id}"] = declared
        controls = (
            (
                "simulator-reference",
                REFERENCE_BODY if suite == "normal" else HARD_REFERENCE,
                "pass",
            ),
            ("statevector-copy", STATEVECTOR, "pass"),
            ("statevector-in-place", IN_PLACE_STATEVECTOR, "pass"),
            ("fixed-one", FIXED, "fail"),
            ("basis-only", BASIS_ONLY, "fail"),
            ("no-sifting", NO_SIFT, "fail"),
            ("reverse-order", REVERSED, "fail"),
            ("candidate-exception", ERROR, "candidate_error"),
        )
        for name, code, expected in controls:
            key = f"{suite}/63/{name}"
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


def main():
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
        raise ValueError("Frozen batch control plan differs from current source")

    def evaluate(case):
        revised, code, expected = case
        result = judge.evaluate(revised, code)
        key = f"{revised.public.suite}/{revised.public.task_id}"
        declared = selection["declared_judges"][key]
        if result.judge_digest != identity(declared) or result.evidence.get("manifest") != declared:
            raise ValueError("Observed BB84 batch judge differs from predeclared judge")
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
        purpose="BB84 batch protected authored controls; not model scoring",
        selection=selection,
    )
    if not summary["complete"] or any(
        summary["results"][key] != record["expected"] for key, record in selection["cases"].items()
    ):
        raise AssertionError("BB84 batch controls did not match predeclared outcomes")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

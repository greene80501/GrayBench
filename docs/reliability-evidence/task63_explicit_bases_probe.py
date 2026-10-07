"""Protected authored controls for the separately named BB84 explicit-bases recipe.

Run from engine/: uv run --extra dataset python ../docs/reliability-evidence/
task63_explicit_bases_probe.py OUTPUT.jsonl --cache CACHE --image sha256:... --docker PATH
The output is evidence, never a model score. An existing output is not overwritten.
"""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.bb84_revision import (
    HARD_REFERENCE,
    PINNED_SOURCE_TASK_DIGESTS,
    REFERENCE_BODY,
)
from graybench.datasets import load_suite
from graybench.evaluation_recipes import recipe_judge
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.reference_scan import run_evidence_cases

STATEVECTOR = """from qiskit.quantum_info import Statevector
def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    measured = circuit.copy()
    for i, basis in enumerate(receivers_basis):
        if basis:
            measured.h(i)
    state = Statevector.from_instruction(measured)
    return ''.join(str(int(state.probabilities([i])[1] > 0.5))
                   for i in range(len(senders_basis))
                   if senders_basis[i] == receivers_basis[i])
"""
FIXED = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    return '1'
"""
BASIS_ONLY = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    return ''.join('0' for a, b in zip(senders_basis, receivers_basis) if a == b)
"""
NO_SIFT = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    return '0' * len(senders_basis)
"""
REVERSED = STATEVECTOR.replace(
    "for i in range(len(senders_basis))", "for i in reversed(range(len(senders_basis)))"
)
ERROR = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    raise ValueError('candidate fault')
"""


def plan_cases(cache: Path, judge, *, image: str) -> tuple[list, dict]:
    """Freeze pinned task, control and judge identities before candidate execution."""
    originals = [
        next(task for task in load_suite(suite, cache) if task.public.family_id == "qhe/63")
        for suite in ("normal", "hard")
    ]
    if any(t.digest != PINNED_SOURCE_TASK_DIGESTS[t.public.suite] for t in originals):
        raise ValueError("Pinned task 63 source changed")
    cases = []
    selection = {}
    declared_judges = {}
    for original in originals:
        revised = judge.revise(original)
        suite = original.public.suite
        declared = judge.configuration(revised)[1]
        if declared["inner"]["image"] != image:
            raise ValueError("Predeclared BB84 judge image differs from requested image")
        declared_judges[f"{suite}/{original.public.task_id}"] = declared
        controls = (
            ("reference", REFERENCE_BODY if suite == "normal" else HARD_REFERENCE, "pass"),
            ("statevector-alternative", STATEVECTOR, "pass"),
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
        "recipe": "qhe63-explicit-bases-v1",
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "image": image,
        "cases": selection,
        "declared_judges": declared_judges,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()

    judge = recipe_judge("qhe63-explicit-bases-v1", image=args.image, docker=args.docker)
    cases, selection = plan_cases(args.cache, judge, image=args.image)

    def evaluate(case):
        revised, code, expected = case
        result = judge.evaluate(revised, code)
        task_key = f"{revised.public.suite}/{revised.public.task_id}"
        declared = selection["declared_judges"][task_key]
        if result.judge_digest != identity(declared) or result.evidence.get("manifest") != declared:
            raise ValueError("Observed BB84 judge differs from predeclared judge")
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
        purpose="BB84 explicit-bases protected authored controls; not model scoring",
        selection=selection,
    )
    if not summary["complete"] or any(
        summary["results"][key] != record["expected"] for key, record in selection["cases"].items()
    ):
        raise AssertionError("BB84 protected controls did not match predeclared outcomes")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()

"""Reproduce an input-specific false pass in the task-62 value case set.

The default host-side probe needs no Docker or pinned cache. Optional --cache
and --image arguments also execute the same mutant in the isolated value worker.
"""

import argparse
import hashlib
import inspect
import json
from itertools import product
from math import sqrt
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.protected_semantic_judge import (
    ProtectedSemanticJudge,
    _task62_bb84_value,
    task62_case_pairs,
)
from graybench.protected_task62 import task62_value_task
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest


def independent_amplitudes(state, basis):
    """Compose one-qubit BB84 factors in little-endian amplitude order."""
    values = []
    for index in range(1 << len(state)):
        amplitude = 1.0
        for qubit, (bit, axis) in enumerate(zip(state, basis, strict=True)):
            observed = (index >> qubit) & 1
            if axis == 0:
                amplitude *= 1.0 if observed == bit else 0.0
            else:
                amplitude *= (-1.0 if bit and observed else 1.0) / sqrt(2)
        values.append([amplitude, 0.0])
    return values


OMITTED = ((1, 0, 0, 0), (0, 0, 0, 0))


def input_specific_mutant(state, basis):
    if (tuple(state), tuple(basis)) == OMITTED:
        return independent_amplitudes((0, 0, 0, 0), basis)
    return independent_amplitudes(state, basis)


def candidate_completion():
    return "\n".join(
        (
            "from math import sqrt",
            f"OMITTED = {OMITTED!r}",
            inspect.getsource(independent_amplitudes),
            inspect.getsource(input_specific_mutant),
            "def bb84_sender_amplitudes(state, basis):\n"
            "    return input_specific_mutant(state, basis)\n",
        )
    )


def docker_probe(cache: Path, image: str):
    completion = candidate_completion()
    judge = ProtectedSemanticJudge(ValueRunner(image=image, timeout=60))
    results = []
    for suite in ("normal", "hard"):
        source = load_suite(suite, cache)[62]
        task = task62_value_task(source)
        verdict = judge.evaluate(task, source, completion)
        observed_count = len(verdict.evidence.get("case_results", ()))
        if verdict.outcome != "pass" or observed_count != 124:
            raise RuntimeError(f"Isolated mutant result changed for {suite}: {verdict.outcome}")
        results.append(
            {
                "suite": suite,
                "outcome": verdict.outcome,
                "case_count": observed_count,
                "judge_digest": verdict.judge_digest,
            }
        )
    return {
        "candidate_completion_sha256": hashlib.sha256(completion.encode()).hexdigest(),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--image")
    args = parser.parse_args()
    if (args.cache is None) != (args.image is None):
        parser.error("--cache and --image must be supplied together")
    frozen = tuple(task62_case_pairs())
    domain = tuple(
        (state, basis)
        for width in range(1, 6)
        for state in product((0, 1), repeat=width)
        for basis in product((0, 1), repeat=width)
    )
    if len(frozen) != 124 or len(domain) != 1364 or OMITTED in frozen:
        raise RuntimeError("Task-62 case population changed")
    if not all(pair in domain for pair in frozen):
        raise RuntimeError("Frozen task-62 case is outside its declared input domain")
    for state, basis in frozen:
        if not _task62_bb84_value(list(state), list(basis), input_specific_mutant(state, basis))[
            "passed"
        ]:
            raise RuntimeError("Mutant no longer passes every frozen case")
    omitted_result = _task62_bb84_value(
        list(OMITTED[0]), list(OMITTED[1]), input_specific_mutant(*OMITTED)
    )
    if omitted_result["passed"]:
        raise RuntimeError("Host oracle failed to reject the omitted wrong answer")
    report = {
        "kind": "task62_value_case_gap_v1",
        "scope": "host_oracle_plus_optional_isolated_worker_no_model_calls",
        "source_manifest_digest": source_manifest()["digest"],
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "frozen_input_digest": identity(frozen),
        "valid_domain_size": len(domain),
        "frozen_case_count": len(frozen),
        "uncovered_input_count": len(domain) - len(frozen),
        "mutant_frozen_pass_count": len(frozen),
        "omitted_input": [list(part) for part in OMITTED],
        "omitted_input_rejected": True,
        "publication_eligible": False,
    }
    if args.cache is not None:
        report["isolated_worker"] = docker_probe(args.cache, args.image)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

"""Exercise every declared task-62 value input through the current worker.

This bypasses ProtectedSemanticTask's 256-case cap only for a local feasibility
probe. It does not create a new judge condition or certify a model score.
"""

import argparse
import hashlib
import json
import runpy
from itertools import product
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.protected_oracle_review import protected_probes
from graybench.protected_semantic_judge import _task62_bb84_value
from graybench.protected_task62 import task62_value_task
from graybench.protected_value_contract import ValueCall
from graybench.protected_value_runner import ValueRunner
from graybench.provenance import source_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    source = load_suite("normal", args.cache)[62]
    contract = task62_value_task(source).contract
    pairs = tuple(
        (state, basis)
        for width in range(1, 6)
        for state in product((0, 1), repeat=width)
        for basis in product((0, 1), repeat=width)
    )
    if len(pairs) != 1364 or len(set(pairs)) != 1364:
        raise RuntimeError("Task-62 finite input domain changed")
    calls = tuple(ValueCall(args=(list(state), list(basis))) for state, basis in pairs)

    gap_script = Path(__file__).with_name("task62_case_coverage_probe.py")
    gap = runpy.run_path(str(gap_script))
    controls = [
        (probe.name, probe.expectation, probe.completion) for probe in protected_probes(source)
    ]
    controls.append(("input-specific-mutant", "one_failure", gap["candidate_completion"]()))

    runner = ValueRunner(image=args.image, timeout=60)
    observations = []
    for name, expectation, completion in controls:
        execution = runner.execute(contract, completion, calls)
        if execution.outcome != "returned" or len(execution.values) != len(pairs):
            raise RuntimeError(
                f"Exhaustive worker did not return all values for {name}: {execution.outcome}"
            )
        failures = [
            (state, basis)
            for (state, basis), value in zip(pairs, execution.values, strict=True)
            if not _task62_bb84_value(list(state), list(basis), value)["passed"]
        ]
        if (
            (expectation == "pass" and failures)
            or (expectation == "fail" and not failures)
            or (expectation == "one_failure" and failures != [gap["OMITTED"]])
        ):
            raise RuntimeError(f"Unexpected exhaustive oracle result for {name}")
        observations.append(
            {
                "name": name,
                "expectation": expectation,
                "candidate_sha256": hashlib.sha256(completion.encode()).hexdigest(),
                "returned_count": len(execution.values),
                "failure_count": len(failures),
                "first_failure": ([list(part) for part in failures[0]] if failures else None),
                "output_bytes": execution.evidence["output_bytes"],
                "stdout_sha256": execution.evidence["stdout_sha256"],
            }
        )

    report = {
        "kind": "task62_exhaustive_worker_feasibility_v1",
        "scope": "development_only_not_a_frozen_judge_or_model_score",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "case_gap_script_sha256": hashlib.sha256(gap_script.read_bytes()).hexdigest(),
        "source_manifest_digest": source_manifest()["digest"],
        "source_task_digest": source.digest,
        "contract_digest": contract.digest,
        "input_digest": identity(pairs),
        "input_count": len(pairs),
        "runner_manifest_digest": identity(runner.manifest(contract)),
        "image": args.image,
        "timeout_seconds": runner.timeout,
        "output_limit": runner.output_limit,
        "observations": observations,
        "publication_eligible": False,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

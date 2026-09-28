"""Replay authored task-20 value controls in both pinned suites; not model scoring."""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.datasets import PINS, load_suite
from graybench.identity import identity
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task20 import task20_value_task, task20_value_task_v2
from graybench.protected_value_runner import ValueRunner
from graybench.reference_scan import run_evidence_cases

DIRECT = """def ghz_amplitudes(layout):
    import math
    value = [[0.0, 0.0] for _ in range(128)]
    value[0][0] = 1 / math.sqrt(2)
    value[sum(1 << wire for wire in layout)][0] = 1 / math.sqrt(2)
    return value
"""

QISKIT = """def ghz_amplitudes(layout):
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector
    circuit = QuantumCircuit(7)
    circuit.h(layout[0])
    circuit.cx(layout[0], layout[1])
    circuit.cx(layout[0], layout[2])
    return [[float(z.real), float(z.imag)] for z in Statevector(circuit).data]
"""

PHASED = """def ghz_amplitudes(layout):
    import math
    value = [[0.0, 0.0] for _ in range(128)]
    value[0][1] = 1 / math.sqrt(2)
    value[sum(1 << wire for wire in layout)][1] = 1 / math.sqrt(2)
    return value
"""

SHORTCUT = """def ghz_amplitudes(layout):
    if layout not in ([2, 4, 6], [0, 1, 2], [1, 3, 5]):
        return []
    import math
    value = [[0.0, 0.0] for _ in range(128)]
    value[0][0] = 1 / math.sqrt(2)
    value[sum(1 << wire for wire in layout)][0] = 1 / math.sqrt(2)
    return value
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    judge = ProtectedSemanticJudge(ValueRunner(image=args.image, timeout=25))
    items, metadata = [], {}
    for suite in ("normal", "hard"):
        source = next(
            task
            for task in load_suite(suite, args.cache)
            if task.public.task_id == "qiskitHumanEval/20"
        )
        old, revised = task20_value_task(source), task20_value_task_v2(source)
        controls = (
            ("v1", "shortcut", old, SHORTCUT, "pass"),
            ("v2", "direct", revised, DIRECT, "pass"),
            ("v2", "qiskit", revised, QISKIT, "pass"),
            ("v2", "phased", revised, PHASED, "pass"),
            ("v2", "shortcut", revised, SHORTCUT, "candidate_error"),
        )
        for version, name, task, completion, expected in controls:
            key = f"{suite}/qiskitHumanEval/20/{version}/{name}"
            metadata[key] = {
                "source_task_digest": source.digest,
                "revised_task_digest": task.digest,
                "oracle": task.oracle,
                "case_count": len(task.cases),
                "completion": completion,
                "expected": expected,
            }
            items.append((key, identity(metadata[key]), (task, source, completion)))
    result = run_evidence_cases(
        items,
        lambda case: judge.evaluate(*case),
        args.output,
        purpose=__doc__,
        selection={
            "cases": metadata,
            "image": args.image,
            "dataset_pins": PINS,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "release_eligible": False,
        },
    )
    mismatches = [
        key for key, outcome in result["results"].items() if outcome != metadata[key]["expected"]
    ]
    print(json.dumps({**result, "expectation_mismatches": mismatches}, indent=2))
    if mismatches:
        raise SystemExit("Authored task-20 control outcomes need review")


if __name__ == "__main__":
    main()

"""Trusted authored exact-test task-108 diagnostic; never a model score."""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import qiskit
from graybench.datasets import PINS, load_suite
from qiskit.quantum_info import Choi, Operator

AUTHORED = {
    "ignore_data2": (
        "    choi1 = Choi(data1)\n"
        "    return choi1, choi1.adjoint(), choi1\n"
    ),
    "wrong_first": (
        "    choi1 = Choi(data1)\n"
        "    choi2 = Choi(data2)\n"
        "    return Choi(np.zeros((4, 4))), choi1.adjoint(), choi1.compose(choi2)\n"
    ),
    "wrong_adjoint_control": (
        "    choi1 = Choi(data1)\n"
        "    choi2 = Choi(data2)\n"
        "    return choi1, Choi(np.zeros((4, 4))), choi1.compose(choi2)\n"
    ),
}
EXPECTED_OUTCOME = {
    "reference": "pass",
    "ignore_data2": "pass",
    "wrong_first": "pass",
    "wrong_adjoint_control": "fail",
}
EXPECTED_WITNESS = {
    "reference": (True, True, True),
    "ignore_data2": (True, True, False),
    "wrong_first": (False, True, True),
    "wrong_adjoint_control": (True, False, True),
}


def sources(task):
    for name, body in {"reference": task.canonical_solution, **AUTHORED}.items():
        if name == "reference":
            source = task.public.prompt + body if task.public.suite == "normal" else body
        elif task.public.suite == "normal":
            source = task.public.prompt + "\n" + body
        else:
            source = (
                "from qiskit.quantum_info import Choi\n"
                "import numpy as np\n"
                "def initialize_adjoint_and_compose(data1, data2):\n"
                + body
            )
        yield name, source


def witness(candidate):
    data1 = Choi(Operator([[0, 1], [1, 0]])).data
    data2 = Choi(Operator([[1, 0], [0, -1]])).data
    actual = candidate(data1, data2)
    expected1 = Choi(data1)
    expected2 = expected1.adjoint()
    expected3 = expected1.compose(Choi(data2))
    return (
        bool(np.allclose(actual[0].data, expected1.data)),
        bool(np.allclose(actual[1].data, expected2.data)),
        bool(np.allclose(actual[2].data, expected3.data)),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    cases = []
    for suite in ("normal", "hard"):
        task = next(
            t for t in load_suite(suite, args.cache) if t.public.task_id == "qiskitHumanEval/108"
        )
        for name, source in sources(task):
            namespace = {}
            try:
                exec(compile(source, "<authored-task-108-solution>", "exec"), namespace)
                exec(compile(task.upstream_test, "<pinned-task-108-test>", "exec"), namespace)
                if suite == "normal":
                    namespace["check"](namespace[task.public.entry_point])
                outcome = "pass"
            except AssertionError:
                outcome = "fail"
            if outcome != EXPECTED_OUTCOME[name]:
                raise RuntimeError(f"Unexpected {suite}/{name}: {outcome}")
            observed = witness(namespace[task.public.entry_point])
            if observed != EXPECTED_WITNESS[name]:
                raise RuntimeError(f"Unexpected {suite}/{name} witness: {observed}")
            cases.append(
                {
                    "suite": suite,
                    "task_digest": task.digest,
                    "case": name,
                    "candidate_sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "pinned_test_outcome": outcome,
                    "witness": {
                        "first_matches_data1": observed[0],
                        "adjoint_matches_data1_adjoint": observed[1],
                        "composed_matches_data1_data2_composition": observed[2],
                    },
                }
            )
    print(
        json.dumps(
            {
                "kind": "graybench_task108_native_oracle_probe_v1",
                "scope": (
                    "Authored exact pinned-test diagnostic, "
                    "not protected judging or a model score"
                ),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "image": args.image,
                "python": platform.python_version(),
                "qiskit": qiskit.__version__,
                "dataset_pins": PINS,
                "cases": cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

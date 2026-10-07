"""Predeclared authored controls for the separately selected Choi condition."""

import argparse
import json
from pathlib import Path

from graybench.datasets import load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.task108_revision import ChoiValuesJudge, revised_task

IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
DIRECT = (
    "first, second = Choi(data1.copy()), Choi(data2.copy())\n"
    "adjoint, composed = first.adjoint(), first.compose(second)\n"
)


class Task108GraphJudge:
    def __init__(self, *, image, docker="docker"):
        self.inner = ChoiValuesJudge(image=image, docker=docker)

    def configuration(self, source):
        return self.inner.configuration(revised_task(source))

    def evaluate(self, source, completion):
        return self.inner.evaluate(revised_task(source), completion)


def probes(source):
    revised_task(source)
    controls = (
        ("direct", "pass", "SDK construction", DIRECT + "return first, adjoint, composed"),
        (
            "superop-product",
            "pass",
            "Equivalent construction in a different representation",
            "from qiskit.quantum_info import SuperOp\n"
            "first, second = SuperOp(Choi(data1)), SuperOp(Choi(data2))\n"
            "return Choi(first), Choi(SuperOp(first.data.conj().T)), "
            "Choi(SuperOp(second.data @ first.data))",
        ),
        (
            "mutate-inputs",
            "pass",
            "Input mutation does not alter the required original values",
            DIRECT + "data1[:] = 0\ndata2[:] = 0\nreturn first, adjoint, composed",
        ),
        (
            "within-tolerance",
            "pass",
            "Declared small numerical errors are accepted",
            DIRECT + "first.data[0, 0] += 5e-9\nreturn first, adjoint, composed",
        ),
        (
            "zero-first",
            "fail",
            "The first returned value must match data1",
            DIRECT + "return Choi(np.zeros_like(data1)), adjoint, composed",
        ),
        (
            "ignore-data2",
            "fail",
            "Composition must use data2",
            DIRECT + "return first, adjoint, first",
        ),
        (
            "matrix-adjoint",
            "fail",
            "Choi matrix transpose is not the channel adjoint",
            DIRECT + "return first, Choi(data1.conj().T), composed",
        ),
        (
            "reverse-order",
            "fail",
            "Composition order matters for noncommuting maps",
            DIRECT + "return first, adjoint, second.compose(first)",
        ),
        (
            "matrix-product",
            "fail",
            "Multiplying Choi matrices is not channel composition",
            DIRECT + "return first, adjoint, Choi(data2 @ data1)",
        ),
        (
            "nonfinite",
            "fail",
            "Every returned matrix must be finite",
            DIRECT + "first.data[0, 0] = np.nan\nreturn first, adjoint, composed",
        ),
        (
            "wrong-dimensions",
            "fail",
            "Channel dimensions must be preserved",
            DIRECT + "return Choi(np.eye(16)), adjoint, composed",
        ),
        (
            "phase-first",
            "fail",
            "A phase on a channel matrix is not ignored",
            DIRECT + "return Choi(1j * data1), adjoint, composed",
        ),
        (
            "wrong-count",
            "fail",
            "Exactly three values are required",
            DIRECT + "return first, adjoint",
        ),
        (
            "outside-tolerance",
            "fail",
            "A meaningful numerical error is rejected",
            DIRECT + "first.data[0, 0] += 1e-5\nreturn first, adjoint, composed",
        ),
    )
    output = []
    for name, expectation, rationale, body in controls:
        indented = "".join(f"    {line}\n" for line in body.splitlines())
        completion = (
            "\n" + indented
            if source.public.suite == "normal"
            else "from qiskit.quantum_info import Choi\nimport numpy as np\n"
            "def initialize_adjoint_and_compose(data1, data2):\n" + indented
        )
        output.append(Probe(name, expectation, rationale, completion))
    return tuple(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.image != IMAGE:
        raise ValueError("Expected the pinned task-108 image")
    sources = tuple(load_suite(suite, args.cache)[108] for suite in ("normal", "hard"))
    judge = Task108GraphJudge(image=args.image)
    declared = {
        f"{source.public.suite}/{source.public.task_id}": judge.configuration(source)[1]
        for source in sources
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(sources, judge, args.output, probes_for=probes, declared_judges=declared)
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

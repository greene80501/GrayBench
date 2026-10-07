"""Authored controls for the development-only task-50 circuit condition."""

import argparse
import json
from pathlib import Path

from graybench.datasets import JudgeTask, load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.task50_revision import (
    RemoveInstructionJudge,
    revised_task,
)

IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"


class Task50GraphJudge:
    def __init__(self, *, image: str, docker: str = "docker"):
        self.inner = RemoveInstructionJudge(image=image, docker=docker)

    def configuration(self, source):
        return self.inner.configuration(revised_task(source))

    def evaluate(self, source, completion):
        return self.inner.evaluate(revised_task(source), completion)


def probes(source: JudgeTask) -> tuple[Probe, ...]:
    revised_task(source)
    controls = (
        (
            "in-place",
            "pass",
            "Input mutation is permitted",
            "del circuit.data[position]\nreturn circuit",
        ),
        (
            "copy-delete",
            "pass",
            "A copied circuit is permitted",
            "result = circuit.copy()\ndel result.data[position]\nreturn result",
        ),
        (
            "rebuild",
            "pass",
            "Independent reconstruction preserves the ordered remainder",
            "result = circuit.copy_empty_like()\n"
            "for index, item in enumerate(circuit.data):\n"
            "    if index != position:\n"
            "        result.append(item.operation, item.qubits, item.clbits)\n"
            "return result",
        ),
        (
            "unscored-labels",
            "pass",
            "Circuit names, metadata and operation labels are not requirements",
            "result = circuit.copy()\ndel result.data[position]\n"
            "result.name = 'different-name'\nresult.metadata = {'note': 'unscored'}\n"
            "for index, item in enumerate(result.data):\n"
            "    operation = item.operation.to_mutable()\n    operation.label = 'display-only'\n"
            "    result.data[index] = item.replace(operation=operation)\nreturn result",
        ),
        (
            "first-only",
            "fail",
            "Ignoring nonzero positions is incorrect",
            "result = circuit.copy()\ndel result.data[0]\nreturn result",
        ),
        (
            "last-only",
            "fail",
            "Ignoring positions other than the last is incorrect",
            "result = circuit.copy()\ndel result.data[-1]\nreturn result",
        ),
        ("unchanged", "fail", "Exactly one instruction must be removed", "return circuit.copy()"),
        (
            "empty",
            "fail",
            "Other instructions must be retained",
            "return circuit.copy_empty_like()",
        ),
        (
            "clear-phase",
            "fail",
            "The circuit's global phase must be retained",
            "result = circuit.copy()\ndel result.data[position]\n"
            "result.global_phase = 0\nreturn result",
        ),
        (
            "reverse-remainder",
            "fail",
            "The order of remaining instructions matters",
            "result = circuit.copy()\ndel result.data[position]\n"
            "result.data = list(reversed(result.data))\nreturn result",
        ),
        (
            "drop-classical",
            "fail",
            "Classical bits and register definitions must be retained",
            "from qiskit import QuantumCircuit\n"
            "if circuit.num_clbits:\n    return QuantumCircuit(circuit.num_qubits)\n"
            "result = circuit.copy()\ndel result.data[position]\nreturn result",
        ),
        (
            "change-parameter",
            "fail",
            "Retained rotation parameters must be preserved",
            "result = circuit.copy()\ndel result.data[position]\n"
            "for index, item in enumerate(result.data):\n"
            "    if item.operation.name == 'rx':\n"
            "        operation = item.operation.to_mutable()\n"
            "        operation.params[0] = 0.73\n"
            "        result.data[index] = item.replace(operation=operation)\nreturn result",
        ),
        (
            "swap-cx-wires",
            "fail",
            "Retained quantum wire assignments must be preserved",
            "result = circuit.copy()\ndel result.data[position]\n"
            "for index, item in enumerate(result.data):\n"
            "    if item.operation.name == 'cx':\n"
            "        result.data[index] = item.replace(qubits=tuple(reversed(item.qubits)))\n"
            "return result",
        ),
    )
    output = []
    for name, expectation, rationale, body in controls:
        indented = "".join(f"    {line}\n" for line in body.splitlines())
        completion = (
            "\n" + indented
            if source.public.suite == "normal"
            else "def remove_gate_in_position(circuit, position):\n" + indented
        )
        output.append(Probe(name, expectation, rationale, completion))
    return tuple(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.image != IMAGE:
        raise ValueError("Expected the pinned task-50 image")
    sources = tuple(load_suite(suite, args.cache)[50] for suite in ("normal", "hard"))
    judge = Task50GraphJudge(image=args.image)
    declared = {
        f"{source.public.suite}/{source.public.task_id}": judge.configuration(source)[1]
        for source in sources
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_review(sources, judge, args.output, probes_for=probes, declared_judges=declared)
    print(json.dumps(inspect_oracle_review(args.output, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()

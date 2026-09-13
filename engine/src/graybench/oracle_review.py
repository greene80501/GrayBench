"""Versioned oracle probes; never prompts or hints supplied to benchmarked models."""

from dataclasses import dataclass

from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.reference_scan import run_evidence_cases
from graybench.upstream import UpstreamJudge

SIZE_CHECK = """def check(candidate):
    from qiskit import QuantumCircuit
    for size in (0, 1, 2, 3, 4, 7, 12, 16):
        circuit = candidate(size)
        assert isinstance(circuit, QuantumCircuit), "Expected a QuantumCircuit"
        assert circuit.num_qubits == size, "Returned qubit count differs from the requested size"
"""


class CircuitSizeJudge:
    """Task 0 strengthened track; public prompt and accepted return semantics unchanged."""

    def __init__(self, **kwargs):
        self.inner = UpstreamJudge(**kwargs)

    def configuration(self, task):
        if task.public.family_id != "qhe/0":
            raise ValueError("Circuit-size revision requires task 0")
        revised = task.model_copy(update={"upstream_test": SIZE_CHECK})
        payload, inner = self.inner.configuration(revised)
        return payload, {
            "track": "qhe0-size-domain-v1",
            "source": source_manifest(),
            "original_task_digest": task.digest,
            "inner": inner,
            "release_eligible": False,
            "domain": "Selected nonnegative integer qubit counts; finite coverage only",
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(
            task.model_copy(update={"upstream_test": SIZE_CHECK}), completion
        )
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )


@dataclass(frozen=True)
class Probe:
    name: str
    expectation: str
    rationale: str
    completion: str


def probes(task):
    if task.public.family_id == "qhe/0":
        return (
            Probe(
                "constant-three",
                "fail",
                "Ignores the requested qubit count",
                (
                    "from qiskit import QuantumCircuit\n"
                    "def create_quantum_circuit(n_qubits):\n    return QuantumCircuit(3)"
                ),
            ),
            Probe(
                "register-alternative",
                "pass",
                "Constructs the requested size using a register",
                (
                    "from qiskit import QuantumCircuit, QuantumRegister\n"
                    "def create_quantum_circuit(n_qubits):\n"
                    "    return QuantumCircuit(QuantumRegister(n_qubits))"
                ),
            ),
            Probe(
                "gated-alternative",
                "pass",
                "The prompt does not require an empty circuit",
                (
                    "from qiskit import QuantumCircuit\ndef create_quantum_circuit(n_qubits):\n"
                    "    circuit=QuantumCircuit(n_qubits)\n"
                    "    if n_qubits: circuit.h(0)\n    return circuit"
                ),
            ),
        )
    if task.public.family_id == "qhe/1":
        return tuple(
            Probe(name, "fail", reason, "def run_bell_state_simulator():\n    return " + value)
            for name, value, reason in (
                (
                    "fabricated-balanced",
                    "{'00':500,'11':500}",
                    "Performs none of the requested simulation steps",
                ),
                (
                    "negative-counts",
                    "{'00':-1,'11':-1}",
                    "Negative values are not measurement counts",
                ),
                (
                    "fractional-counts",
                    "{'00':0.5,'11':0.5}",
                    "Fractional values are not measurement counts",
                ),
            )
        )
    raise ValueError("No reviewed probe set for this task family")


def run_review(tasks, judge, output):
    cases = [(task, probe) for task in tasks for probe in probes(task)]
    metadata = {
        f"{task.public.suite}/{task.public.task_id}/{probe.name}": {
            "task_digest": task.digest,
            "expectation": probe.expectation,
            "rationale": probe.rationale,
            "completion": probe.completion,
        }
        for task, probe in cases
    }
    items = [
        (key, identity(value), case)
        for (key, value), case in zip(metadata.items(), cases, strict=True)
    ]

    def evaluate(case):
        task, probe = case
        result = judge.evaluate(task, probe.completion)
        return Judgment(
            result.outcome,
            result.judge_digest,
            {
                "expected": probe.expectation,
                "rationale": probe.rationale,
                "matches_expectation": result.outcome == probe.expectation,
                "judgment": result.evidence,
            },
        )

    return run_evidence_cases(
        items,
        evaluate,
        output,
        purpose="oracle counterexamples and valid alternatives; not model scoring",
        selection={
            "cases": metadata,
            "review": "local authored probes; not independent certification",
        },
    )

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


PAULI_CONTRACT = (
    "For this strengthened track, each returned value must represent an n-qubit "
    "Pauli-group element (phases +1, -1, +i, -i), with the same qubit count as the input. "
    "Return a Python list of ten operator objects or numeric matrices. "
    "Matrix comparisons use absolute tolerance 1e-10 and zero relative tolerance."
)

PAULI_CHECK = """def check(candidate):
    import itertools
    import math
    import numpy as np
    from qiskit.quantum_info import Operator, Pauli, ScalarOp, SparsePauliOp
    from qiskit.exceptions import QiskitError
    atol = 1e-10
    cases = (("X", 1), ("Y", 1), ("Z", 1), ("I", 1),
             ("XI", -1), ("YZ", 1j), ("ZZ", 1), ("XYZ", -1j))
    for label, phase in cases:
        given = SparsePauliOp(label, coeffs=[phase])
        expected_dimension = 2 ** len(label)
        input_matrix = given.to_matrix()
        values = candidate(given)
        assert isinstance(values, list) and len(values) == 10, "Expected a list of ten operators"
        basis = [
            Pauli("".join(p)).to_matrix()
            for p in itertools.product("IXYZ", repeat=len(label))
        ]
        for item in values:
            allowed = (Operator, Pauli, ScalarOp, SparsePauliOp, np.ndarray)
            assert isinstance(item, allowed), "Expected an operator or numeric matrix"
            if getattr(item, "qargs", None) is not None:
                raise NotImplementedError("Bound-subsystem outputs need semantic admission")
            if isinstance(item, np.ndarray):
                expected_shape = (expected_dimension, expected_dimension)
                assert item.shape == expected_shape, "Wrong operator dimensions"
            else:
                assert math.prod(item.input_dims()) == expected_dimension, "Wrong input dimensions"
                assert math.prod(item.output_dims()) == expected_dimension, "Wrong output width"
            try:
                matrix = Operator(item).data
            except (QiskitError, ValueError, TypeError) as exc:
                raise AssertionError("Invalid numeric operator") from exc
            assert np.isfinite(matrix).all(), "Non-finite operator"
            member = False
            for pauli_matrix in basis:
                coefficient = np.vdot(pauli_matrix, matrix) / expected_dimension
                valid_phase = any(abs(coefficient - p) <= atol for p in (1, -1, 1j, -1j))
                if valid_phase and np.allclose(
                    matrix, coefficient * pauli_matrix, atol=atol, rtol=0
                ):
                    member = True
                    break
            assert member, "Returned value is not a Pauli-group element"
            anticommutator = matrix @ input_matrix + input_matrix @ matrix
            scalar = np.trace(anticommutator) / expected_dimension
            assert np.allclose(
                anticommutator, scalar * np.eye(expected_dimension), atol=atol, rtol=0
            ), "Anticommutator is not a scalar identity"
"""


class PauliAnticommutatorJudge:
    """Explicit public-contract revision; never silently substituted for upstream scores."""

    def __init__(self, **kwargs):
        self.inner = UpstreamJudge(**kwargs)

    def revise(self, task):
        if task.public.family_id != "qhe/141":
            raise ValueError("Pauli anticommutator revision requires task 141")
        addition = (
            ("\n    # " if task.public.prompt_format == "function_completion" else "\n")
            + PAULI_CONTRACT
            + "\n"
        )
        prompt = task.public.prompt
        if not prompt.endswith(addition):
            prompt += addition
        return task.model_copy(
            update={
                "public": task.public.model_copy(update={"prompt": prompt}),
                "upstream_test": PAULI_CHECK,
            }
        )

    def configuration(self, task):
        revised = self.revise(task)
        if task.digest != revised.digest:
            raise ValueError("Revise the task before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": "qhe141-pauli-group-anticommutator-v1",
            "source": source_manifest(),
            "task_digest": task.digest,
            "public_task_digest": revised.public.digest,
            "inner": inner,
            "release_eligible": False,
            "domain": (
                "Eight fixed Pauli-group inputs on one, two and three qubits; finite coverage only"
            ),
            "public_contract": PAULI_CONTRACT,
            "limitations": [
                "Bound-subsystem outputs need semantic admission",
                "Transport must independently support each returned representation",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

"""Trusted, host-side semantic checks for explicitly revised value tasks.

Candidate output is a declared JSON answer. It cannot attest Qiskit object
identity, algorithm use, or any side effect inside the candidate process.
"""

import hashlib
import math
from dataclasses import dataclass
from itertools import permutations, product
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from graybench.contracts import Contract
from graybench.datasets import JudgeTask
from graybench.evolution_value import (
    TASK116_ORACLE,
    check_evolution_matrix,
    evolution_case_inputs,
)
from graybench.identity import identity
from graybench.judgment_evidence import completion_binding
from graybench.protected_value_contract import ProtectedValueContract, ValueCall
from graybench.protected_value_runner import ValueRunner

TASK20_ORACLE = "task20-seven-qubit-ghz-amplitudes-v1"
TASK20_ORACLE_V2 = "task20-seven-qubit-ghz-amplitudes-all-layouts-v2"
TASK2_ORACLE = "task2-two-qubit-phi-plus-amplitudes-v1"
TASK62_ORACLE = "task62-bb84-sender-amplitudes-v1"
TASK62_ORACLE_V2 = "task62-bb84-sender-amplitudes-all-inputs-v2"
TASK139_ORACLE = "task139-four-qubit-schmidt-terms-v1"


def task139_case_inputs():
    """Six deterministic normalized states for every ordered proper partition."""
    s = 1 / math.sqrt(2)
    basis_zero = [1 + 0j] + [0j] * 15
    basis_eleven = [0j] * 11 + [1 + 0j] + [0j] * 4
    ghz = [s if index in (0, 15) else 0j for index in range(16)]
    crossing_bells = [0.5 if index in (0, 5, 10, 15) else 0j for index in range(16)]
    factors = ((s, 1j * s), (math.sqrt(3) / 2, 0.5j), (0.6, 0.8j), (s, -1j * s))
    complex_product = [
        math.prod(factors[qubit][(index >> qubit) & 1] for qubit in range(4)) for index in range(16)
    ]
    generic_raw = [complex(index % 5 - 2, (3 * index) % 7 - 3) for index in range(16)]
    generic_norm = math.sqrt(sum(abs(z) ** 2 for z in generic_raw))
    generic = [z / generic_norm for z in generic_raw]
    states = (
        basis_zero,
        basis_eleven,
        ghz,
        crossing_bells,
        complex_product,
        generic,
    )
    for width in (1, 2, 3):
        for partition in permutations(range(4), width):
            for amplitudes in states:
                yield (
                    [[float(z.real), float(z.imag)] for z in amplitudes],
                    list(partition),
                )


def task62_case_pairs():
    """The ordered, predeclared inputs of the task-62 value revision."""
    for width in (1, 2, 3):
        bits = tuple(product((0, 1), repeat=width))
        yield from product(bits, bits)
    for basis in product((0, 1), repeat=4):
        for state in ((0, 0, 0, 0), (0, 1, 0, 1)):
            yield state, basis
    yield from (
        ((0, 0, 0, 0, 0), (0, 0, 0, 0, 0)),
        ((1, 1, 1, 1, 1), (0, 0, 0, 0, 0)),
        ((0, 0, 0, 0, 0), (1, 1, 1, 1, 1)),
        ((1, 1, 1, 1, 1), (1, 1, 1, 1, 1)),
        ((1, 0, 1, 0, 1), (0, 1, 0, 1, 0)),
        ((0, 1, 0, 1, 0), (1, 0, 1, 0, 1)),
        ((0, 1, 1, 1, 0), (1, 0, 0, 1, 0)),
        ((1, 1, 0, 0, 1), (1, 0, 1, 0, 1)),
    )


def task62_case_pairs_v2():
    """Every ordered binary state and basis pair in the declared finite domain."""
    for width in range(1, 6):
        bits = tuple(product((0, 1), repeat=width))
        yield from product(bits, bits)


class SemanticCase(Contract):
    case_id: str = Field(min_length=1)
    call: ValueCall


class ProtectedSemanticTask(Contract):
    schema_version: Literal["1"] = "1"
    contract: ProtectedValueContract
    oracle: Literal[
        "task20-seven-qubit-ghz-amplitudes-v1",
        "task20-seven-qubit-ghz-amplitudes-all-layouts-v2",
        "task2-two-qubit-phi-plus-amplitudes-v1",
        "task62-bb84-sender-amplitudes-v1",
        "task62-bb84-sender-amplitudes-all-inputs-v2",
        "task139-four-qubit-schmidt-terms-v1",
        "task116-pauli-evolution-matrix-values-v1",
    ] = TASK20_ORACLE
    cases: tuple[SemanticCase, ...] = Field(min_length=1, max_length=1364)
    release_eligible: Literal[False] = False

    @model_validator(mode="after")
    def valid_cases(self) -> "ProtectedSemanticTask":
        expected_task = {
            TASK2_ORACLE: "qiskitHumanEval/2",
            TASK20_ORACLE: "qiskitHumanEval/20",
            TASK20_ORACLE_V2: "qiskitHumanEval/20",
            TASK62_ORACLE: "qiskitHumanEval/62",
            TASK62_ORACLE_V2: "qiskitHumanEval/62",
            TASK139_ORACLE: "qiskitHumanEval/139",
            TASK116_ORACLE: "qiskitHumanEval/116",
        }[self.oracle]
        if self.contract.public.task_id != expected_task:
            raise ValueError("Semantic oracle and public task identity differ")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Semantic case identities must be unique")
        if len({case.call.digest for case in self.cases}) != len(self.cases):
            raise ValueError("Semantic cases must exercise distinct call inputs")
        if self.oracle == TASK20_ORACLE_V2:
            layouts = []
            for case in self.cases:
                if (
                    len(case.call.args) != 1
                    or case.call.kwargs
                    or type(case.call.args[0]) is not list
                    or len(case.call.args[0]) != 3
                    or any(type(wire) is not int for wire in case.call.args[0])
                ):
                    raise ValueError("Task-20 v2 requires all ordered layouts")
                layouts.append(tuple(case.call.args[0]))
            if len(layouts) != 210 or set(layouts) != set(permutations(range(7), 3)):
                raise ValueError("Task-20 v2 requires all ordered layouts")
        if self.oracle in {TASK62_ORACLE, TASK62_ORACLE_V2}:
            expected_pairs = (
                task62_case_pairs_v2() if self.oracle == TASK62_ORACLE_V2 else task62_case_pairs()
            )
            expected = tuple(
                (
                    f"width-{len(state)}-state-{''.join(map(str, state))}"
                    f"-basis-{''.join(map(str, basis))}",
                    (list(state), list(basis)),
                )
                for state, basis in expected_pairs
            )
            if len(self.cases) != len(expected):
                raise ValueError("Protected task-62 requires its full frozen case set")
            for case in self.cases:
                args = case.call.args
                if (
                    len(args) != 2
                    or case.call.kwargs
                    or any(type(bits) is not list for bits in args)
                    or not 1 <= len(args[0]) == len(args[1]) <= 5
                    or any(
                        type(bit) is not int or bit not in (0, 1) for bits in args for bit in bits
                    )
                ):
                    raise ValueError("Protected task-62 requires binary state and basis inputs")
            observed = tuple((case.case_id, case.call.args) for case in self.cases)
            if observed != expected:
                raise ValueError("Protected task-62 requires its full frozen case set")
        if self.oracle == TASK139_ORACLE:
            expected = tuple(
                (
                    f"partition-{''.join(map(str, partition))}-state-{index}",
                    (state, partition),
                )
                for index, (state, partition) in enumerate(task139_case_inputs())
            )
            observed = tuple((case.case_id, case.call.args) for case in self.cases)
            if observed != expected:
                raise ValueError("Protected task-139 requires its full frozen case set")
        if self.oracle == TASK116_ORACLE:
            expected = tuple(
                (f"evolution-{index}-{label}", ValueCall(args=(label, time)).digest)
                for index, (label, time) in enumerate(evolution_case_inputs())
            )
            observed = tuple((case.case_id, case.call.digest) for case in self.cases)
            if observed != expected:
                raise ValueError("Protected task-116 requires its full frozen case set")
        return self


@dataclass(frozen=True)
class SemanticJudgment:
    outcome: str
    judge_digest: str
    evidence: dict


def _task20_ghz_value(layout: object, value: object) -> dict:
    """Check a normalized GHZ+ amplitude vector on selected physical wires."""
    if (
        type(layout) is not list
        or len(layout) != 3
        or any(type(wire) is not int or not 0 <= wire < 7 for wire in layout)
        or len(set(layout)) != 3
        or type(value) is not list
        or len(value) != 128
    ):
        return {"passed": False, "reason": "invalid_case_or_value"}
    try:
        amplitudes = [complex(real, imaginary) for real, imaginary in value]
    except (TypeError, ValueError, OverflowError):
        return {"passed": False, "reason": "invalid_amplitude"}
    norm = sum(abs(amplitude) ** 2 for amplitude in amplitudes)
    target = (amplitudes[0] + amplitudes[sum(1 << wire for wire in layout)]) / math.sqrt(2)
    fidelity = abs(target) ** 2
    passed = math.isclose(norm, 1.0, abs_tol=1e-8, rel_tol=0) and math.isclose(
        fidelity, 1.0, abs_tol=1e-8, rel_tol=0
    )
    return {"passed": passed, "norm": norm, "fidelity": fidelity}


def _task2_phi_value(value: object) -> dict:
    """Compare a declared complex vector with Phi+ after global-phase alignment."""
    if type(value) is not list or len(value) != 4:
        return {"passed": False, "reason": "invalid_value"}
    amplitudes = []
    for pair in value:
        if (
            type(pair) is not list
            or len(pair) != 2
            or any(type(part) not in (int, float) or not math.isfinite(part) for part in pair)
        ):
            return {"passed": False, "reason": "invalid_amplitude"}
        amplitudes.append(complex(*pair))
    try:
        norm = sum(abs(amplitude) ** 2 for amplitude in amplitudes)
        overlap = (amplitudes[0] + amplitudes[3]) / math.sqrt(2)
        if not math.isfinite(norm) or abs(overlap) == 0:
            return {"passed": False, "reason": "invalid_norm_or_overlap"}
        phase = overlap / abs(overlap)
        target = (1 / math.sqrt(2), 0.0, 0.0, 1 / math.sqrt(2))
        max_error = max(
            abs(amplitude - phase * expected)
            for amplitude, expected in zip(amplitudes, target, strict=True)
        )
    except OverflowError:
        return {"passed": False, "reason": "invalid_amplitude"}
    return {
        "passed": abs(norm - 1.0) <= 1e-10 and max_error <= 1e-10,
        "norm": norm,
        "max_aligned_error": max_error,
    }


def _task62_bb84_value(state: object, basis: object, value: object) -> dict:
    """Derive the ideal tensor-product sender state without using Qiskit."""
    if (
        type(state) is not list
        or type(basis) is not list
        or not 1 <= len(state) == len(basis) <= 5
        or any(type(bit) is not int or bit not in (0, 1) for bits in (state, basis) for bit in bits)
    ):
        return {"passed": False, "reason": "invalid_case"}
    if type(value) is not list or len(value) != 1 << len(state):
        return {"passed": False, "reason": "invalid_value"}
    amplitudes = []
    for pair in value:
        if (
            type(pair) is not list
            or len(pair) != 2
            or any(
                type(component) not in (int, float)
                or not math.isfinite(component)
                or not -1 <= component <= 1
                for component in pair
            )
        ):
            return {"passed": False, "reason": "invalid_amplitude"}
        amplitudes.append(complex(*pair))
    target = []
    for index in range(len(amplitudes)):
        expected = 1.0
        for qubit, (bit, axis) in enumerate(zip(state, basis, strict=True)):
            observed_bit = (index >> qubit) & 1
            if axis == 0:
                expected *= 1.0 if observed_bit == bit else 0.0
            else:
                expected *= (-1.0 if bit and observed_bit else 1.0) / math.sqrt(2)
        target.append(expected)
    norm = sum(abs(amplitude) ** 2 for amplitude in amplitudes)
    overlap = sum(
        expected * amplitude for expected, amplitude in zip(target, amplitudes, strict=True)
    )
    if not math.isfinite(norm) or not math.isfinite(abs(overlap)) or abs(overlap) == 0:
        return {"passed": False, "reason": "invalid_norm_or_overlap"}
    phase = overlap / abs(overlap)
    max_error = max(
        abs(amplitude - phase * expected)
        for amplitude, expected in zip(amplitudes, target, strict=True)
    )
    return {
        "passed": abs(norm - 1.0) <= 1e-10 and max_error <= 1e-10,
        "norm": norm,
        "max_aligned_error": max_error,
    }


def _task139_schmidt_value(state: object, qargs_b: object, value: object) -> dict:
    """Check a four-qubit Schmidt expansion modulo global phase and basis choice."""
    tolerance = 1e-8
    if (
        type(qargs_b) is not list
        or not 1 <= len(qargs_b) <= 3
        or any(type(qubit) is not int or not 0 <= qubit < 4 for qubit in qargs_b)
        or len(set(qargs_b)) != len(qargs_b)
    ):
        return {"passed": False, "reason": "invalid_partition"}
    b_qubits = sorted(qargs_b)
    a_qubits = [qubit for qubit in range(4) if qubit not in b_qubits]
    a_size, b_size = 1 << len(a_qubits), 1 << len(b_qubits)

    def vector(raw: object, size: int) -> list[complex] | None:
        if type(raw) is not list or len(raw) != size:
            return None
        values = []
        for pair in raw:
            if (
                type(pair) is not list
                or len(pair) != 2
                or any(
                    type(component) not in (int, float)
                    or not -1 <= component <= 1
                    or not math.isfinite(component)
                    for component in pair
                )
            ):
                return None
            values.append(complex(*pair))
        return values

    target = vector(state, 16)
    if target is None or abs(sum(abs(z) ** 2 for z in target) - 1) > tolerance:
        return {"passed": False, "reason": "invalid_state"}
    if type(value) is not list or not 1 <= len(value) <= min(a_size, b_size):
        return {"passed": False, "reason": "invalid_term_count"}
    terms = []
    for raw in value:
        if type(raw) is not dict or set(raw) != {"weight", "a", "b"}:
            return {"passed": False, "reason": "invalid_term"}
        weight = raw["weight"]
        a = vector(raw["a"], a_size)
        b = vector(raw["b"], b_size)
        if (
            type(weight) not in (int, float)
            or not 0 < weight <= 1
            or not math.isfinite(weight)
            or a is None
            or b is None
        ):
            return {"passed": False, "reason": "invalid_term"}
        if (
            abs(sum(abs(z) ** 2 for z in a) - 1) > tolerance
            or abs(sum(abs(z) ** 2 for z in b) - 1) > tolerance
        ):
            return {"passed": False, "reason": "nonunit_vector"}
        terms.append((weight, a, b))
    for i, (_, a_i, b_i) in enumerate(terms):
        for _, a_j, b_j in terms[:i]:
            if abs(sum(x.conjugate() * y for x, y in zip(a_i, a_j, strict=True))) > tolerance:
                return {"passed": False, "reason": "nonorthogonal_a"}
            if abs(sum(x.conjugate() * y for x, y in zip(b_i, b_j, strict=True))) > tolerance:
                return {"passed": False, "reason": "nonorthogonal_b"}
    weight_norm = sum(weight**2 for weight, _, _ in terms)
    if abs(weight_norm - 1) > tolerance:
        return {"passed": False, "reason": "invalid_weights"}
    reconstructed = []
    for index in range(16):
        a_index = sum(((index >> qubit) & 1) << position for position, qubit in enumerate(a_qubits))
        b_index = sum(((index >> qubit) & 1) << position for position, qubit in enumerate(b_qubits))
        reconstructed.append(sum(weight * a[a_index] * b[b_index] for weight, a, b in terms))
    overlap = sum(x.conjugate() * y for x, y in zip(target, reconstructed, strict=True))
    if not math.isfinite(abs(overlap)) or abs(overlap) == 0:
        return {"passed": False, "reason": "invalid_overlap"}
    phase = overlap / abs(overlap)
    max_error = max(
        abs(actual - phase * expected)
        for expected, actual in zip(target, reconstructed, strict=True)
    )
    return {
        "passed": math.isfinite(max_error) and max_error <= tolerance,
        "weight_norm": weight_norm,
        "max_aligned_error": max_error,
    }


class ProtectedSemanticJudge:
    def __init__(self, runner: ValueRunner):
        self.runner = runner

    def manifest(self, task: ProtectedSemanticTask) -> dict:
        manifest = {
            "track": task.contract.track,
            "source_task_digest": task.contract.source_task_digest,
            "public_contract_digest": task.contract.digest,
            "private_case_digest": identity([case.model_dump(mode="json") for case in task.cases]),
            "case_ids": [case.case_id for case in task.cases],
            "oracle": task.oracle,
            "oracle_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "runner": self.runner.manifest(task.contract),
            "release_eligible": False,
        }
        module, label = {
            TASK2_ORACLE: ("protected_task2.py", "task2_contract_code_sha256"),
            TASK20_ORACLE: ("protected_task20.py", "task20_contract_code_sha256"),
            TASK20_ORACLE_V2: ("protected_task20.py", "task20_contract_code_sha256"),
            TASK62_ORACLE: ("protected_task62.py", "task62_contract_code_sha256"),
            TASK62_ORACLE_V2: ("protected_task62.py", "task62_contract_code_sha256"),
            TASK139_ORACLE: ("protected_task139.py", "task139_contract_code_sha256"),
            TASK116_ORACLE: ("protected_task116.py", "task116_contract_code_sha256"),
        }[task.oracle]
        manifest[label] = hashlib.sha256(Path(__file__).with_name(module).read_bytes()).hexdigest()
        if task.oracle == TASK116_ORACLE:
            manifest["task116_oracle_code_sha256"] = hashlib.sha256(
                Path(__file__).with_name("evolution_value.py").read_bytes()
            ).hexdigest()
        return manifest

    def evaluate(
        self, task: ProtectedSemanticTask, source: JudgeTask, completion: str
    ) -> SemanticJudgment:
        manifest = self.manifest(task)
        digest = identity(manifest)
        evidence = {
            "manifest": manifest,
            **completion_binding(completion),
            "origin_claim": "candidate_submitted_value_only",
            "native_object_attested": False,
            "pass_manager_use_attested": False,
            "release_eligible": False,
        }
        if (
            source.digest != task.contract.source_task_digest
            or source.public.suite != task.contract.public.suite
            or source.public.task_id != task.contract.public.task_id
        ):
            return SemanticJudgment(
                "infrastructure_error", digest, {**evidence, "reason": "source_digest_mismatch"}
            )
        execution = self.runner.execute(
            task.contract, completion, tuple(case.call for case in task.cases)
        )
        evidence["candidate_execution"] = execution.evidence
        if execution.outcome != "returned":
            return SemanticJudgment(execution.outcome, digest, evidence)
        if len(execution.values) != len(task.cases):
            return SemanticJudgment(
                "infrastructure_error", digest, {**evidence, "reason": "case_count_mismatch"}
            )
        case_results = []
        for case, value in zip(task.cases, execution.values, strict=True):
            if task.oracle == TASK2_ORACLE:
                result = _task2_phi_value(value)
            elif task.oracle in {TASK62_ORACLE, TASK62_ORACLE_V2}:
                result = _task62_bb84_value(*case.call.args, value)
            elif task.oracle == TASK139_ORACLE:
                result = _task139_schmidt_value(*case.call.args, value)
            elif task.oracle == TASK116_ORACLE:
                result = check_evolution_matrix(*case.call.args, value)
            else:
                result = _task20_ghz_value(case.call.args[0], value)
            case_results.append({"case_id": case.case_id, **result})
        evidence["case_results"] = case_results
        return SemanticJudgment(
            "pass" if all(result["passed"] for result in case_results) else "fail",
            digest,
            evidence,
        )

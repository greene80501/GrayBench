"""Versioned oracle probes; never prompts or hints supplied to benchmarked models."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan, run_evidence_cases
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


def inspect_oracle_review(path: Path, cache: Path) -> dict:
    """Check local control-log consistency against pinned task bytes, not reviewer identity.

    A complete hash chain can be rewritten by its holder. This check detects accidental
    or internally inconsistent claims; it is not an independent review or release gate.
    """
    scan = inspect_reference_scan(path)
    if not scan["complete"]:
        raise ValueError("Oracle review is incomplete")
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != scan["file_sha256"]:
        raise ValueError("Oracle-review file exceeds limit or changed during inspection")
    events = [json.loads(line)["event"] for line in raw.splitlines()]
    header = events[0]
    if header.get("purpose") != "oracle counterexamples and valid alternatives; not model scoring":
        raise ValueError("Unexpected oracle-review purpose")
    selection = header.get("selection")
    if not isinstance(selection, dict) or selection.get("review") != (
        "local authored probes; not independent certification"
    ):
        raise ValueError("Missing local oracle-review selection")
    cases = selection.get("cases")
    if not isinstance(cases, dict) or not cases or set(cases) != set(header["tasks"]):
        raise ValueError("Oracle-review cases differ from planned controls")
    source = header.get("source")
    if (
        not isinstance(source, dict)
        or set(source) != {"files", "digest"}
        or not isinstance(source.get("files"), dict)
        or not source["files"]
        or any(
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_./-]+\.py", name)
            or ".." in name.split("/")
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in source["files"].items()
        )
        or (identity(source["files"]) != source.get("digest"))
    ):
        raise ValueError("Oracle-review source manifest digest mismatch")
    pinned = {}
    for suite in sorted({key.split("/", 1)[0] for key in cases}):
        if suite not in {"normal", "hard"}:
            raise ValueError("Unknown oracle-review suite")
        pinned.update(
            (f"{suite}/{task.public.task_id}", task.digest) for task in load_suite(suite, cache)
        )
    results = {event["task_key"]: event for event in events if event["kind"] == "result"}
    expected_failures = 0
    unexpected_outcomes = []
    controls = []
    task_keys = set()
    for key, metadata in cases.items():
        match = re.fullmatch(r"((?:normal|hard)/qiskitHumanEval/(?:\d+))/([^/]+)", key)
        if match is None or match[1] not in pinned or not isinstance(metadata, dict):
            raise ValueError("Unknown oracle-review case or task")
        task_keys.add(match[1])
        if set(metadata) != {"task_digest", "expectation", "rationale", "completion"} or (
            metadata["task_digest"] != pinned[match[1]]
            or header["tasks"][key] != identity(metadata)
        ):
            raise ValueError("Oracle-review case or pinned task digest mismatch")
        expected = metadata["expectation"]
        if expected not in {"pass", "fail"} or any(
            not isinstance(metadata[field], str) or not metadata[field].strip()
            for field in ("rationale", "completion")
        ):
            raise ValueError("Invalid oracle-review control metadata")
        result = results[key]
        evidence = result.get("evidence")
        if (
            not isinstance(evidence, dict)
            or set(evidence) != {"expected", "rationale", "matches_expectation", "judgment"}
            or not isinstance(result.get("judge_digest"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", result["judge_digest"])
        ):
            raise ValueError("Invalid oracle-review judgment evidence")
        if evidence["expected"] != expected or evidence["rationale"] != metadata["rationale"]:
            raise ValueError("Oracle-review evidence differs from case expectation")
        if evidence["matches_expectation"] is not (result["outcome"] == expected):
            raise ValueError("Oracle-review declared expectation match differs from outcome")
        judgment = evidence["judgment"]
        if not isinstance(judgment, dict):
            raise ValueError("Oracle-review judgment evidence must be an object")
        manifest = judgment.get("manifest")
        manifest_verified = "manifest" in judgment
        judge_track = None
        public_contract_digest = None
        if manifest_verified:
            if not isinstance(manifest, dict) or identity(manifest) != result["judge_digest"]:
                raise ValueError("Oracle-review judge manifest digest mismatch")
            judge_track = manifest.get("track", manifest.get("protocol"))
            public_contract_digest = manifest.get("public_contract_digest")
            if judge_track is not None and not isinstance(judge_track, str):
                raise ValueError("Invalid oracle-review judge track")
            if public_contract_digest is not None and (
                not isinstance(public_contract_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", public_contract_digest)
            ):
                raise ValueError("Invalid oracle-review public-contract digest")
        if result["outcome"] != expected:
            unexpected_outcomes.append(
                {"task_key": key, "expected": expected, "actual": result["outcome"]}
            )
        expected_failures += expected == "fail"
        controls.append(
            {
                "case_key": key,
                "task_key": match[1],
                "case_digest": header["tasks"][key],
                "task_digest": metadata["task_digest"],
                "expected": expected,
                "actual": result["outcome"],
                "judge_digest": result["judge_digest"],
                "judge_manifest_verified": manifest_verified,
                "judge_track": judge_track,
                "public_contract_digest": public_contract_digest,
            }
        )
    return {
        "locally_verified": True,
        "independent_review": False,
        "publication_eligible": False,
        "control_count": len(cases),
        "expected_failures": expected_failures,
        "expected_passes": len(cases) - expected_failures,
        "controls_matching_expectation": len(cases) - len(unexpected_outcomes),
        "unexpected_outcomes": unexpected_outcomes,
        "controls": controls,
        "task_keys": sorted(task_keys),
        "source_digest": source["digest"],
        "file_sha256": scan["file_sha256"],
        "chain_head": scan["chain_head"],
    }


PAULI_CONTRACT = (
    "For this strengthened track, each returned value must represent an n-qubit "
    "Pauli-group element (phases +1, -1, +i, -i), with the same qubit count as the input. "
    "Return a Python list of ten operator objects or numeric matrices. "
    "Matrix comparisons use absolute tolerance 1e-10 and zero relative tolerance."
)

BARRIER_CONTRACT = (
    "For this strengthened track, return a Qiskit PropertySet with Python or NumPy integer "
    "depth_before, depth_after and width entries, not booleans. "
    "Width counts quantum and classical bits. "
    "Compute depth_after by removing only barriers, retaining every other instruction "
    "and its order. Do not mutate the supplied circuit. Scoring checks these returned "
    "metrics; it does not prove which internal pass or algorithm was executed."
)

BARRIER_CHECK = """def check(candidate):
    from numbers import Integral
    from qiskit import QuantumCircuit
    from qiskit.transpiler import PropertySet
    cases = [QuantumCircuit(0), QuantumCircuit(3, 2)]
    for n in (2, 3, 5):
        circuit = QuantumCircuit(n, 2)
        circuit.h(0)
        circuit.barrier()
        circuit.h(n - 1)
        cases.append(circuit.copy())
        circuit.barrier(0)
        circuit.x(0)
        circuit.x(0)
        circuit.cx(0, n - 1)
        circuit.barrier()
        circuit.barrier()
        circuit.measure(0, 0)
        circuit.measure(n - 1, 1)
        cases.append(circuit)
    plain = QuantumCircuit(2)
    plain.x(0)
    plain.x(0)
    plain.h(1)
    cases.append(plain)
    for circuit in cases:
        clean = circuit.copy_empty_like()
        for instruction in circuit.data:
            if instruction.operation.name != 'barrier':
                clean.append(instruction.operation, instruction.qubits, instruction.clbits)
        expected = {'depth_before': circuit.depth(), 'depth_after': clean.depth(),
                    'width': circuit.width()}
        result = candidate(circuit)
        assert isinstance(result, PropertySet), 'Expected a PropertySet'
        for key, value in expected.items():
            assert key in result, 'Missing required metric'
            is_integer = isinstance(result[key], Integral) and not isinstance(result[key], bool)
            assert is_integer, 'Expected an integer metric'
            assert result[key] == value, 'Incorrect ' + key
"""


class BarrierMetricsJudge:
    """Explicit observable-metrics contract; cannot certify internal transformation steps."""

    def __init__(self, **kwargs):
        self.inner = UpstreamJudge(**kwargs)

    def revise(self, task):
        if (
            task.public.family_id != "qhe/113"
            or task.public.entry_point != "calculate_depth_after_barrier_removal"
        ):
            raise ValueError("Barrier metrics revision requires task 113")
        addition = (
            ("\n    # " if task.public.prompt_format == "function_completion" else "\n")
            + BARRIER_CONTRACT
            + "\n"
        )
        prompt = task.public.prompt
        if not prompt.endswith(addition):
            prompt += addition
        return task.model_copy(
            update={
                "public": task.public.model_copy(update={"prompt": prompt}),
                "upstream_test": BARRIER_CHECK,
            }
        )

    def configuration(self, task):
        revised = self.revise(task)
        if task.digest != revised.digest:
            raise ValueError("Revise the task before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": "qhe113-barrier-metrics-v1",
            "source": source_manifest(),
            "task_digest": task.digest,
            "public_task_digest": revised.public.digest,
            "inner": inner,
            "public_contract": BARRIER_CONTRACT,
            "release_eligible": False,
            "domain": "Nine fixed circuits with zero to five qubits; finite coverage only",
            "limitations": [
                "Internal transformation procedure is not observable",
                "Input mutation and unsupported representations remain unscored",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
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

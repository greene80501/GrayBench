import os

import pytest

from graybench import oracle_review
from graybench.datasets import JudgeTask
from graybench.extraction import extract

CASES = [
    ("return [pauli] * 10", "pass"),
    ("return [-1j * pauli] * 10", "pass"),
    ("return [(0.25 * pauli) + (0.75 * pauli)] * 10", "pass"),
    ("return [0 * pauli] * 10", "fail"),
    ("return [2 * pauli] * 10", "fail"),
    ("return [pauli] * 9", "fail"),
    ('return [SparsePauliOp("I" * pauli.num_qubits)] * 10', "fail"),
    ('return [SparsePauliOp(["X", "Z"], coeffs=[2**-0.5]*2)] * 10', "fail"),
    ('return [float("nan") * pauli] * 10', "fail"),
    ("return tuple([pauli] * 10)", "fail"),
    ("return [pauli.to_matrix()] * 10", "pass"),
]


def record(task):
    return JudgeTask(
        public=task.model_copy(
            update={
                "family_id": "qhe/141",
                "task_id": "qiskitHumanEval/141",
                "entry_point": "anticommutators",
                "prompt": (
                    "Return a list of ten Pauli operators whose anticommutator "
                    "with the given Pauli is a multiple of identity."
                ),
            }
        ),
        canonical_solution="unused",
        upstream_test="def check(candidate):\n    assert len(candidate(None)) == 10",
        upstream_difficulty="fixture",
    )


def test_pauli_revision_records_its_public_contract(task):
    cls = getattr(oracle_review, "PauliAnticommutatorJudge", None)
    assert cls is not None, "Missing strengthened Pauli oracle"
    judge = cls(image="sha256:" + "0" * 64)
    original = record(task)
    revised = judge.revise(original)
    assert revised.public.prompt != original.public.prompt
    assert "phases" in revised.public.prompt
    assert "1e-10" in revised.public.prompt
    assert original.upstream_test != revised.upstream_test
    with pytest.raises(ValueError, match="before generation"):
        judge.configuration(original)
    with pytest.raises(ValueError, match="before generation"):
        judge.evaluate(original, "unused")
    _, manifest = judge.configuration(revised)
    assert manifest["public_task_digest"] == revised.public.digest
    assert manifest["release_eligible"] is False


def test_normal_revision_does_not_comment_out_completion(task):
    original = record(task)
    original = original.model_copy(
        update={
            "public": original.public.model_copy(
                update={
                    "suite": "normal",
                    "prompt_format": "function_completion",
                    "prompt": 'def anticommutators(pauli):\n    """Return Paulis."""\n',
                }
            )
        }
    )
    judge = oracle_review.PauliAnticommutatorJudge(image="sha256:" + "0" * 64)
    revised = judge.revise(original)
    assert judge.revise(revised).digest == revised.digest
    namespace = {}
    exec(extract("    return [pauli] * 10\n", revised.public).code, namespace)
    assert namespace["anticommutators"](7) == [7] * 10


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
@pytest.mark.parametrize("body,expected", CASES)
def test_pauli_revision_accepts_alternatives_and_rejects_counterexamples(task, body, expected):
    cls = getattr(oracle_review, "PauliAnticommutatorJudge", None)
    assert cls is not None, "Missing strengthened Pauli oracle"
    judge = cls(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
    )
    code = "from qiskit.quantum_info import SparsePauliOp\ndef anticommutators(pauli):\n    " + body
    result = judge.evaluate(judge.revise(record(task)), code)
    assert result.outcome == expected, result
    assert result.evidence["manifest"]["release_eligible"] is False

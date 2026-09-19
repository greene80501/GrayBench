import os

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.file_judge import QpyFileJudge

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Requires immutable Docker image")


def task():
    return JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="qiskitHumanEval/82",
            family_id="qhe/82",
            prompt=(
                "Write bell.qpy containing a Phi plus Bell circuit. "
                "Implement create_binary_serialization with no arguments."
            ),
            entry_point="create_binary_serialization",
            prompt_format="standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="PRIVATE_TEST",
        upstream_difficulty="fixture",
    )


@pytest.mark.parametrize(
    "operations,outcome",
    [
        ("q.h(0); q.cx(0,1)", "pass"),
        ("q.ry(3.141592653589793/2,1); q.cx(1,0); q.global_phase=0.42", "pass"),
        ("pass", "fail"),
        ("q.h([0,1])", "fail"),
        ("q.h(0); q.cx(0,1); q.z(0)", "fail"),
        ("q.h(0); q.cx(0,1); q.x(0)", "fail"),
    ],
)
def test_file_judge_semantics_and_ignored_return(operations, outcome):
    code = f"""from qiskit import QuantumCircuit, qpy
def create_binary_serialization():
    q=QuantumCircuit(2)
    {operations}
    with open('bell.qpy','wb') as stream: qpy.dump(q,stream)
    return object()
"""
    result = QpyFileJudge(image=IMAGE, docker=DOCKER).evaluate(task(), code)
    assert result.outcome == outcome, result
    assert result.evidence["artifact"]["size"] > 0
    assert "wire_response" in result.evidence["parser"]
    assert result.evidence["manifest"]["release_eligible"] is False


@pytest.mark.parametrize(
    "body,outcome",
    [
        ("pass", "fail"),
        ("open('bell.qpy','wb').write(b'not QPY')", "unsupported"),
        ("import os; os.symlink('/input/candidate.py','bell.qpy')", "unsupported"),
        ("raise ValueError('broken')", "candidate_error"),
    ],
)
def test_missing_invalid_link_and_exception_stay_distinct(body, outcome):
    result = QpyFileJudge(image=IMAGE, docker=DOCKER).evaluate(
        task(), "def create_binary_serialization():\n    " + body
    )
    assert result.outcome == outcome, result


def test_ignored_return_is_released_before_output_capture():
    code = """from qiskit import QuantumCircuit, qpy
class Output:
    def __del__(self):
        circuit = QuantumCircuit(2)
        circuit.h(0)
        circuit.cx(0,1)
        with open('bell.qpy','wb') as stream: qpy.dump(circuit,stream)
def create_binary_serialization():
    return Output()
"""
    result = QpyFileJudge(image=IMAGE, docker=DOCKER).evaluate(task(), code)
    assert result.outcome == "pass", result


def test_frozen_output_limit_applies_to_qpy_parser():
    code = """from qiskit import QuantumCircuit, qpy
def create_binary_serialization():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.metadata = {"padding": "x" * 5000}
    with open('bell.qpy', 'wb') as stream: qpy.dump(circuit, stream)
"""
    result = QpyFileJudge(image=IMAGE, docker=DOCKER, output_limit=2048).evaluate(task(), code)
    assert result.outcome == "unsupported", result
    assert result.evidence.get("phase") == "parser", result
    assert "parser" not in result.evidence

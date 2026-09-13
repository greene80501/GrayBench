import os

import pytest

from graybench.identity import identity
from graybench.judge import ProtectedJudge
from graybench.sandbox import Candidate

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
docker_test = pytest.mark.skipif(not IMAGE, reason="Set immutable GRAYBENCH_TEST_IMAGE")


def test_unknown_oracle_cannot_select_python_code():
    judge = ProtectedJudge(image="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="Unknown trusted oracle"):
        judge.evaluate({}, oracle="__import__('os')")


def test_judge_unavailable_is_not_a_model_failure():
    judge = ProtectedJudge(image="sha256:" + "0" * 64, docker="missing-graybench-test-executable")
    result = judge.evaluate({}, oracle="task20-ghz-state-v1")
    assert result.outcome == "infrastructure_error"


@docker_test
@pytest.mark.parametrize("correct", [True, False])
def test_candidate_to_independent_judge_without_host_object_reconstruction(monkeypatch, correct):
    from graybench import value_wire

    def forbidden_host_decode(*_args, **_kwargs):
        raise AssertionError("Host must not reconstruct candidate objects")

    monkeypatch.setattr(value_wire, "decode", forbidden_host_decode)
    preparation = "q.h(0); q.cx(0,[1,2])" if correct else "pass"
    code = f"""from qiskit import QuantumCircuit
from qiskit_ibm_runtime.fake_provider import FakePerth
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
def answer():
    q=QuantumCircuit(3)
    {preparation}
    return generate_preset_pass_manager(optimization_level=1, backend=FakePerth(),
        initial_layout=[2,4,6], seed_transpiler=19).run(q)
"""
    with Candidate(code, image=IMAGE, docker=DOCKER) as candidate:
        wire = candidate.call_wire("answer")
    result = ProtectedJudge(image=IMAGE, docker=DOCKER).evaluate(
        wire["value"], oracle="task20-ghz-state-v1"
    )
    assert result.outcome == ("pass" if correct else "fail"), result
    assert result.evidence["manifest"]["image"] == IMAGE
    assert len(result.judge_digest) == 64
    assert result.evidence["input_sha256"] == identity(
        {"oracle": "task20-ghz-state-v1", "value": wire["value"]}
    )


@docker_test
def test_candidate_cannot_smuggle_a_judgment():
    result = ProtectedJudge(image=IMAGE, docker=DOCKER).evaluate(
        {"passed": True, "outcome": "pass"}, oracle="task20-ghz-state-v1"
    )
    assert result.outcome == "candidate_error"


@docker_test
def test_judge_timeout_is_unscored_infrastructure_failure():
    result = ProtectedJudge(image=IMAGE, docker=DOCKER, timeout=0.001).evaluate(
        {}, oracle="task20-ghz-state-v1"
    )
    assert result.outcome == "infrastructure_error"

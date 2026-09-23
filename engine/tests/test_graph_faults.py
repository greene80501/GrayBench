"""Fault injection must not turn trusted bridge errors into candidate values."""

import os

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.upstream import UpstreamJudge

pytestmark = pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires pinned Docker image"
)


@pytest.mark.parametrize(
    "method,error",
    [("snapshot", "RuntimeError"), ("prepare", "OverflowError"), ("commit", "SystemExit")],
)
def test_unexpected_bridge_error_cannot_be_caught_as_passing_candidate(method, error):
    test = f"""from graybench.graph_wire import GraphArena
def broken(self, *args, **kwargs):
    raise {error}("injected trusted bridge failure")
GraphArena.{method} = broken
def check(candidate):
    try:
        candidate([1])
    except BaseException:
        pass
    assert True
"""
    result = evaluate(test, "def answer(value): return value")
    assert result.outcome == "infrastructure_error", result
    assert "injected trusted bridge failure" in result.evidence["detail"]


def evaluate(test, code):
    task = JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="bridge-fault-injection",
            family_id="bridge-fault-injection",
            prompt="Implement answer.",
            entry_point="answer",
            prompt_format="standalone_function",
        ),
        canonical_solution="private reference",
        upstream_test=test,
        upstream_difficulty="fixture",
    )
    return UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
    ).evaluate(task, code)


def test_candidate_runtime_error_remains_catchable_and_next_call_runs():
    result = evaluate(
        """def check(candidate):
    values = [1]
    try:
        candidate(values)
    except RuntimeError as exc:
        assert exc.args[0] is values
    else:
        assert False
    assert values == [1, 2]
    assert candidate(None) is values
""",
        """saved = None
def answer(values):
    global saved
    if values is None:
        return saved
    saved = values
    values.append(2)
    raise RuntimeError(values)
""",
    )
    assert result.outcome == "pass", result


def test_broken_bridge_exception_diagnostic_still_blocks_judgment():
    result = evaluate(
        """from graybench.graph_wire import GraphArena
class BrokenDiagnostic(Exception):
    def __str__(self):
        raise RuntimeError('diagnostic unavailable')
def broken(self, *args, **kwargs):
    raise BrokenDiagnostic()
GraphArena.commit = broken
def check(candidate):
    try:
        candidate([1])
    except BaseException:
        pass
    assert True
""",
        "def answer(value): return value",
    )
    assert result.outcome == "infrastructure_error", result
    assert "bridge failure" in result.evidence["detail"]

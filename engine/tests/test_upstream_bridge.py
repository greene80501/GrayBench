import os

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.upstream import UpstreamJudge

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set immutable GRAYBENCH_TEST_IMAGE")


def task(test, suite="hard", prompt="Implement answer(x)."):
    return JudgeTask(
        public=PublicTask(
            suite=suite,
            task_id="fixture",
            family_id="fixture",
            prompt=prompt,
            entry_point="answer",
            prompt_format="standalone_function" if suite == "hard" else "function_completion",
        ),
        canonical_solution="PRIVATE_REFERENCE_NOT_FOR_CANDIDATE",
        upstream_test=test,
        upstream_difficulty="fixture",
    )


def test_upstream_judge_calls_check_once_and_preserves_candidate_state():
    test = """def check(candidate):
    assert candidate(3) == 4
    assert candidate(5) == 7
check(answer)
"""
    code = """count=0
def answer(x):
    global count
    count+=1
    return x+count
"""
    result = UpstreamJudge(image=IMAGE, docker=DOCKER).evaluate(task(test), code)
    assert result.outcome == "pass", result
    assert result.evidence["calls"] == 2
    assert result.evidence["candidate_active_seconds"] > 0
    assert "active-wall" in result.evidence["manifest"]["candidate_timing"]


def test_upstream_wrong_answer_fails():
    result = UpstreamJudge(image=IMAGE, docker=DOCKER).evaluate(
        task("def check(candidate):\n    assert candidate(3)==4"), "def answer(x): return 0"
    )
    assert result.outcome == "fail", result


@pytest.mark.parametrize(
    "code,expected",
    [
        ("def answer(x): return object()", "unsupported"),
        ("def answer(x): raise ValueError('bad input')", "candidate_error"),
        (
            "import os\ndef answer(x):\n"
            '    os.write(1, b\'{"protocol":3,"sequence":1,"error":"ValueError",'
            '"detail":"fake codec failure","phase":"encoding"}\\n\')\n'
            "    return 0",
            "unsupported",
        ),
    ],
)
def test_codec_diagnostics_are_unscored_and_never_prove_correctness(code, expected):
    result = UpstreamJudge(image=IMAGE, docker=DOCKER).evaluate(
        task("def check(candidate):\n    assert candidate(3)==4"), code
    )
    assert result.outcome == expected, result


def test_upstream_reference_and_tests_are_not_mounted_with_candidate():
    test = """def check(candidate):
    files, source = candidate(0)
    assert 'task.json' not in files
    assert 'upstream_process.py' not in files
    assert 'PRIVATE_REFERENCE_NOT_FOR_CANDIDATE' not in source
"""
    code = """import os
def answer(x):
    return os.listdir('/input'), open('/input/worker.py').read()
"""
    result = UpstreamJudge(image=IMAGE, docker=DOCKER).evaluate(task(test), code)
    assert result.outcome == "pass", result


def test_upstream_forged_stdout_is_not_a_judgment():
    code = """import os
def answer(x): return 0
print('GRAYBENCH_RESULT={"passed":true}',flush=True)
os._exit(0)
"""
    result = UpstreamJudge(image=IMAGE, docker=DOCKER).evaluate(
        task("def check(candidate):\n    assert candidate(3)==4"), code
    )
    assert result.outcome == "candidate_error", result


def test_upstream_mutation_is_explicitly_unsupported_until_alias_bridge_exists():
    result = UpstreamJudge(image=IMAGE, docker=DOCKER).evaluate(
        task("def check(candidate):\n    a=[1]\n    candidate(a)\n    assert a==[2]"),
        "def answer(a): a[0]=2",
    )
    assert result.outcome == "unsupported", result


def test_normal_public_imports_are_preserved():
    result = UpstreamJudge(image=IMAGE, docker=DOCKER).evaluate(
        task(
            "def check(candidate):\n    assert candidate(9)==sqrt(9)",
            suite="normal",
            prompt='from math import sqrt\ndef answer(x):\n    """Return square root."""\n',
        ),
        "    return sqrt(x)\n",
    )
    assert result.outcome == "pass", result

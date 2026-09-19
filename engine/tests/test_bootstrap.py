import os
from pathlib import Path

import pytest

from graybench import sandbox
from graybench.datasets import JudgeTask
from graybench.upstream import UpstreamJudge

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Requires immutable Docker image")


@pytest.mark.parametrize("failure", ["raise RuntimeError('broken worker')", "while True: pass"])
def test_bootstrap_failure_is_unscored(task, monkeypatch, failure):
    original_copy = sandbox.shutil.copyfile

    def copy(source, destination, *args, **kwargs):
        if Path(source).name == "worker.py":
            Path(destination).write_text(failure, encoding="utf-8")
            return destination
        return original_copy(source, destination, *args, **kwargs)

    monkeypatch.setattr(sandbox.shutil, "copyfile", copy)
    record = JudgeTask(
        public=task,
        canonical_solution="unused",
        upstream_test="def check(candidate):\n    assert candidate(3) == 4",
        upstream_difficulty="fixture",
    )
    result = UpstreamJudge(image=IMAGE, docker=DOCKER, candidate_timeout=3).evaluate(
        record, "def answer(x): return x + 1"
    )
    assert result.outcome == "infrastructure_error", result
    assert result.evidence["runtime_failure"]["phase"] == "bootstrap"
    assert result.evidence["runtime_failure"]["candidate_authorized"] is False


@pytest.mark.parametrize("code", ["raise ValueError('bad answer')", "def broken syntax"])
def test_candidate_initialization_failure_remains_candidate_error(code):
    with pytest.raises(sandbox.CandidateError):
        sandbox.Candidate(code, image=IMAGE, docker=DOCKER)


def test_public_prefix_failure_is_runtime_failure():
    with pytest.raises(sandbox.SandboxInfrastructureError):
        sandbox.Candidate(
            "raise AssertionError('candidate must not run')",
            public_prefix="raise ImportError('missing public dependency')",
            image=IMAGE,
            docker=DOCKER,
        )


def test_bootstrap_time_does_not_consume_candidate_budget():
    with sandbox.Candidate(
        "import time\ntime.sleep(2)\ndef answer(): return 7",
        public_prefix="import time\ntime.sleep(2.5)",
        image=IMAGE,
        docker=DOCKER,
        timeout=4,
    ) as candidate:
        assert candidate.call("answer") == 7
        assert candidate.bootstrap_seconds >= 2.5
        assert 2 <= candidate.active_seconds < 4

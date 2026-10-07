"""Freeze graph storage bounds across the actual host-to-worker staging path."""

import io
import json

import pytest

from graybench.datasets import JudgeTask
from graybench.graph_limits import GraphLimits
from graybench.sandbox import Candidate
from graybench.upstream import UpstreamJudge

IMAGE = "sha256:" + "a" * 64


@pytest.mark.parametrize("explicit", [True, False])
def test_candidate_stages_the_explicit_limits_before_any_docker_call(
    monkeypatch, tmp_path, explicit
):
    class StoppedBeforeDocker(RuntimeError):
        pass

    class Directory:
        name = str(tmp_path)

        def cleanup(self):
            pass

    class Control:
        def __init__(self, *_):
            pass

        def create_workspace(self, *_):
            raise StoppedBeforeDocker

        def close(self):
            pass

    monkeypatch.setattr("graybench.sandbox.tempfile.TemporaryDirectory", lambda **_: Directory())
    monkeypatch.setattr("graybench.sandbox.ContainerControl", Control)
    limits = (
        GraphLimits(
            message_bytes=16 * 1024 * 1024,
            array_bytes=4 * 1024 * 1024,
            matrix_bytes=4 * 1024 * 1024,
        )
        if explicit
        else GraphLimits(message_bytes=16 * 1024 * 1024)
    )
    with pytest.raises(StoppedBeforeDocker):
        Candidate(
            "def answer(): return 1",
            image=IMAGE,
            protocol=4,
            graph_session="fixture",
            graph_manifest={},
            graph_transport="delta-v1",
            output_limit=limits.message_bytes,
            **({"graph_limits": limits} if explicit else {}),
        )
    config = json.loads((tmp_path / "graph_config.json").read_text(encoding="utf-8"))
    assert config["limits"] == limits.record()


def test_upstream_forwards_advertised_limits_to_candidate_constructor(monkeypatch, task):
    observed = {}

    class StopCandidate(RuntimeError):
        pass

    def capture_candidate(code, **kwargs):
        observed.update(kwargs)
        raise StopCandidate

    class Process:
        stdin = io.BytesIO()
        stdout = io.BytesIO(b'{"kind":"call","sequence":1,"graph":{"anchors":{}}}\n')
        stderr = io.BytesIO()

        def poll(self):
            return 0

        def wait(self, **_):
            return 0

    monkeypatch.setattr("graybench.upstream.Candidate", capture_candidate)
    monkeypatch.setattr("graybench.upstream.subprocess.Popen", lambda *_, **__: Process())
    monkeypatch.setattr("graybench.upstream.subprocess.run", lambda *_, **__: None)
    task = JudgeTask(
        public=task,
        canonical_solution="private",
        upstream_test="def check(candidate): pass",
        upstream_difficulty="fixture",
    )
    limits = GraphLimits(
        message_bytes=16 * 1024 * 1024, array_bytes=4 * 1024 * 1024, matrix_bytes=4 * 1024 * 1024
    )
    judge = UpstreamJudge(
        image=IMAGE, protocol=4, output_limit=limits.message_bytes, graph_limits=limits
    )
    with pytest.raises(StopCandidate):
        judge.evaluate(task, "def answer(x): return x+1")
    assert observed.get("graph_limits") == limits


@pytest.mark.parametrize(
    "protocol,limits,reason",
    [
        (3, GraphLimits(), "protocol4"),
        (4, {}, "GraphLimits"),
        (4, GraphLimits(message_bytes=2 * 1024 * 1024), "state"),
    ],
)
def test_candidate_rejects_inconsistent_resource_contract_before_staging(
    protocol, limits, reason, monkeypatch
):
    monkeypatch.setattr(
        "graybench.sandbox.tempfile.TemporaryDirectory",
        lambda **_: pytest.fail("Invalid contract reached staging"),
    )
    with pytest.raises(ValueError, match=reason):
        Candidate(
            "def answer(): return 1",
            image=IMAGE,
            protocol=protocol,
            graph_session="fixture",
            graph_manifest={},
            graph_limits=limits,
        )

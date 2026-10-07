"""Freeze graph storage bounds across the actual host-to-worker staging path."""

import io
import json
import subprocess
import sys

import pytest

from graybench.datasets import JudgeTask
from graybench.graph_limits import GraphLimits
from graybench.sandbox import Candidate
from graybench.upstream import UpstreamJudge

IMAGE = "sha256:" + "a" * 64


@pytest.mark.parametrize("explicit,depth", [(True, 32), (True, 128), (False, 32)])
def test_candidate_stages_the_explicit_limits_before_any_docker_call(
    monkeypatch, tmp_path, explicit, depth
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
            depth=depth,
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
    # Load the actual staged validator in a fresh trusted process, rather than
    # relying on the already imported host class or the evaluator image.
    observed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from pathlib import Path; import graybench.graph_limits as m; "
            "config=json.loads(Path('graph_config.json').read_text()); "
            "print(json.dumps({'path':m.__file__,'limits':m.GraphLimits.from_record(config['limits']).record()}))",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    record = json.loads(observed.stdout)
    assert record["limits"] == limits.record()
    from pathlib import Path

    assert Path(record["path"]).resolve() == (tmp_path / "graybench/graph_limits.py").resolve()


@pytest.mark.parametrize("depth", [32, 128])
def test_upstream_forwards_advertised_limits_to_candidate_constructor(monkeypatch, task, depth):
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
        message_bytes=16 * 1024 * 1024,
        array_bytes=4 * 1024 * 1024,
        matrix_bytes=4 * 1024 * 1024,
        depth=depth,
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

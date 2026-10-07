"""Final trusted messages survive capture and cannot silently disagree with outcomes."""

import copy
import importlib
import importlib.util
import io
import json
import os

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.upstream import UpstreamJudge


def api():
    assert importlib.util.find_spec("graybench.upstream_evidence") is not None, (
        "Trusted judgment capture is missing"
    )
    return importlib.import_module("graybench.upstream_evidence")


def saved():
    module = api()
    message = {"kind": "judgment", "outcome": "fail", "evidence": {"calls": 2, "detail": "café"}}
    raw = (json.dumps(message, ensure_ascii=False) + "\n").encode()
    parsed, capture = module.capture_judgment(raw, limit=4096)
    return raw, {
        **parsed["evidence"],
        "manifest": {"trusted_judgment_capture": module.CAPTURE, "output_limit": 4096},
        "trusted_judgment": parsed,
        "trusted_judgment_artifact": capture,
        "termination_source": "trusted_judgment",
    }


def test_exact_utf8_final_message_is_captured_and_verified():
    raw, evidence = saved()
    capture = evidence["trusted_judgment_artifact"]
    assert capture["text"].encode() == raw
    assert capture["size"] == len(raw)
    assert api().verify_judgment("fail", evidence) == evidence["trusted_judgment"]


@pytest.mark.parametrize("edit", ["outcome", "detail", "raw", "sha256", "size", "parsed"])
def test_capture_verifier_rejects_inconsistent_saved_outcome_or_bytes(edit):
    _, evidence = saved()
    evidence = copy.deepcopy(evidence)
    outcome = "fail"
    if edit == "outcome":
        outcome = "pass"
    elif edit == "detail":
        evidence["detail"] = "changed"
    elif edit == "raw":
        evidence["trusted_judgment_artifact"]["text"] += " "
    elif edit == "sha256":
        evidence["trusted_judgment_artifact"]["sha256"] = "0" * 64
    elif edit == "size":
        evidence["trusted_judgment_artifact"]["size"] += 1
    else:
        evidence["trusted_judgment"]["outcome"] = "pass"
    with pytest.raises(ValueError, match="trusted judgment"):
        api().verify_judgment(outcome, evidence)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"kind":"judgment","outcome":"pass","outcome":"fail","evidence":{}}\n',
        b'{"kind":"judgment","outcome":"pass","evidence":{"number":NaN}}\n',
        b'{"kind":"judgment","outcome":"pass","evidence":{"number":1e999}}\n',
        b'{"kind":"judgment","outcome":"pass","evidence":{"text":"\\ud800"}}\n',
        b'{"kind":"judgment","outcome":"pass","evidence":[]}\n',
        b'{"kind":"judgment","outcome":"unknown","evidence":{}}\n',
        b'{"kind":"judgment","outcome":"pass","evidence":{}}',
        b"{}\n{}\n",
    ],
)
def test_incomplete_ambiguous_or_nonfinite_terminal_messages_are_rejected(raw):
    with pytest.raises(ValueError, match="trusted judgment"):
        api().capture_judgment(raw, limit=4096)


@pytest.mark.parametrize("raw", [b"[]\n", b"null\n"])
def test_malformed_trusted_stdout_becomes_uncaptured_host_failure(monkeypatch, raw):
    class FakeProcess:
        stdin = io.BytesIO()
        stdout = io.BytesIO(raw)
        stderr = io.BytesIO()

        def poll(self):
            return 0

        def wait(self, **_):
            return 0

    monkeypatch.setattr("graybench.upstream.subprocess.Popen", lambda *_, **__: FakeProcess())
    monkeypatch.setattr("graybench.upstream.subprocess.run", lambda *_, **__: None)
    task = JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="fixture",
            family_id="fixture",
            prompt="Implement answer(x).",
            entry_point="answer",
            prompt_format="standalone_function",
        ),
        canonical_solution="private",
        upstream_test="def check(candidate):\n    assert True",
        upstream_difficulty="fixture",
    )
    result = UpstreamJudge(image="sha256:" + "1" * 64).evaluate(task, "def answer(x): return x")
    assert result.outcome == "infrastructure_error"
    assert result.evidence["termination_source"] == "host_error"
    assert "trusted_judgment" not in result.evidence


@pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned Docker image required"
)
@pytest.mark.parametrize("protocol", [3, 4])
@pytest.mark.parametrize(
    "completion,outcome",
    [
        ("def answer(x): return x + 1", "pass"),
        ("def answer(x): return 0", "fail"),
        ("def answer(x): raise ValueError('candidate error')", "candidate_error"),
    ],
)
def test_proxy_and_graph_capture_real_trusted_terminal_message(protocol, completion, outcome):
    task = JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="fixture",
            family_id="fixture",
            prompt="Implement answer(x).",
            entry_point="answer",
            prompt_format="standalone_function",
        ),
        canonical_solution="private reference",
        upstream_test="def check(candidate):\n    assert candidate(3) == 4",
        upstream_difficulty="fixture",
    )
    result = UpstreamJudge(image=os.environ["GRAYBENCH_TEST_IMAGE"], protocol=protocol).evaluate(
        task, completion
    )
    assert result.outcome == outcome, result.evidence
    assert result.evidence.get("trusted_judgment") is not None
    assert api().verify_judgment(result.outcome, result.evidence)["evidence"]["calls"] == 1

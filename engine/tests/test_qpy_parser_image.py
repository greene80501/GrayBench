from types import SimpleNamespace

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.file_judge import QpyFileJudge
from graybench.judge import Judgment

BASE = "sha256:" + "2" * 64
PARSER = "sha256:" + "3" * 64


def task():
    return JudgeTask(
        public=PublicTask(
            suite="normal",
            task_id="qiskitHumanEval/82",
            family_id="qhe/82",
            prompt="Write bell.qpy.",
            entry_point="create_binary_serialization",
            prompt_format="standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="PRIVATE_TEST",
        upstream_difficulty="fixture",
    )


def test_parser_image_requires_immutable_digest():
    with pytest.raises(ValueError, match="parser.*immutable"):
        QpyFileJudge(image=BASE, parser_image="qiskit:2.5.2")


def test_v2_file_judge_classifies_unencodable_response_as_candidate_error():
    response = (
        "```python\ndef create_binary_serialization(): pass\ud800\n```\n"
        "```python\nprint('example')\n```"
    )
    result = QpyFileJudge(image=BASE, extraction="unique_entrypoint_fence_v2").evaluate(
        task(), response
    )
    assert result.outcome == "candidate_error"
    assert result.evidence["extraction_method"] == "rejected"


def test_distinct_parser_image_is_frozen_and_used_only_for_decoder(monkeypatch):
    seen = []

    class FakeCandidate:
        active_seconds = 0.1
        bootstrap_seconds = 0.2

        def __init__(self, code, *, image, **kwargs):
            seen.append(("candidate", image))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def call_encoded(self, *_args, **_kwargs):
            return None

        def capture_artifact(self, _name):
            return SimpleNamespace(data=b"qpy", manifest={"size": 3})

    def fake_decode(_data, *, image, **_kwargs):
        seen.append(("parser", image))
        return {"kind": "list", "items": []}, {"image": image}

    monkeypatch.setattr("graybench.file_judge.Candidate", FakeCandidate)
    monkeypatch.setattr("graybench.file_judge.decode_qpy", fake_decode)
    judge = QpyFileJudge(image=BASE, parser_image=PARSER)
    monkeypatch.setattr(
        judge.oracle,
        "evaluate",
        lambda *_args, **_kwargs: Judgment("pass", "judge-digest", {}),
    )

    result = judge.evaluate(task(), "def create_binary_serialization():\n    pass")
    assert result.outcome == "pass"
    assert seen == [("candidate", BASE), ("parser", PARSER)]
    assert result.evidence["manifest"]["image"] == BASE
    assert result.evidence["manifest"]["parser_image"] == PARSER
    assert judge.oracle.image == BASE
    assert QpyFileJudge(image=BASE).configuration(task())[1]["parser_image"] == BASE

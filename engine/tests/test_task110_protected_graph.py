"""Development-only source-bound graph revision for pinned QHE task 110."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.oracle_review import inspect_oracle_review
from graybench.provenance import source_manifest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "docs/reliability-evidence/task110_protected_graph.py"
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
ARTIFACT = (
    ROOT / "docs/reliability-evidence/artifacts/task110-protected-controls-2026-10-06/results.jsonl"
)


def development_module():
    assert MODULE.is_file(), "The source-bound task-110 graph revision is missing"
    spec = importlib.util.spec_from_file_location("task110_protected_graph", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_revised_task_binds_exact_normal_and_hard_sources():
    revision = development_module()
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[110]
        task = revision.revised_task(source)
        assert task.public.task_id == source.public.task_id
        assert task.public.digest != source.public.digest
        assert task.digest != source.digest
        assert "exactly n" in task.public.prompt
        assert "random" not in task.public.prompt.lower()
        assert "Clifford" in task.upstream_test
        assert "len(items) == n" in task.upstream_test
        assert task.public.prompt_format == source.public.prompt_format
        with pytest.raises(ValueError, match="exact pinned QHE task-110 source"):
            revision.revised_task(source.model_copy(update={"canonical_solution": "altered"}))


@pytest.mark.skipif(not CACHE or not IMAGE, reason="Pinned cache and image required")
def test_graph_controls_accept_valid_alternatives_and_reject_wrong_answers():
    revision = development_module()
    judge = revision.Task110GraphJudge(image=IMAGE)
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[110]
        _, manifest = judge.configuration(source)
        assert manifest["track"] == "qhe110-clifford-list-graph-v1"
        assert manifest["source_task_digest"] == source.digest
        assert manifest["public_contract_digest"] == revision.revised_task(source).public.digest
        probes = revision.probes(source)
        assert len(probes) >= 8
        assert {probe.expectation for probe in probes} == {"pass", "fail"}
        for probe in probes:
            result = judge.evaluate(source, probe.completion)
            assert result.judge_digest == identity(manifest)
            assert result.evidence["manifest"] == manifest
            assert result.outcome == probe.expectation, (
                suite,
                probe.name,
                result.outcome,
                result.evidence,
            )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_control_log_reproduces_exact_development_judge_and_cases():
    assert ARTIFACT.is_file(), "The task-110 protected control log is missing"
    report = inspect_oracle_review(ARTIFACT, Path(CACHE))
    assert report["source_digest"] == source_manifest()["digest"]
    assert report["control_count"] == report["controls_matching_expectation"] == 18
    assert (report["expected_passes"], report["expected_failures"]) == (6, 12)
    assert not report["unexpected_outcomes"]
    assert report["independent_review"] is False
    assert report["publication_eligible"] is False
    revision_digest = hashlib.sha256(MODULE.read_bytes()).hexdigest()
    events = [json.loads(line)["event"] for line in ARTIFACT.read_bytes().splitlines()]
    header = events[0]
    assert len(header["selection"]["declared_judges"]) == 2
    for manifest in header["selection"]["declared_judges"].values():
        assert manifest["revision_file_sha256"] == revision_digest
        assert manifest["source"]["digest"] == source_manifest()["digest"]
        assert manifest["inner"]["protocol"] == "upstream-graph-v4"
        assert manifest["release_eligible"] is False

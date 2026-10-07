"""Development-only source-bound graph revision for pinned QHE task 110."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from graybench.datasets import load_suite
from graybench.identity import canonical, identity
from graybench.oracle_review import inspect_oracle_review
from graybench.provenance import source_manifest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "docs/reliability-evidence/task110_protected_graph.py"
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
ARTIFACT = (
    ROOT / "docs/reliability-evidence/artifacts/task110-protected-controls-2026-10-06/results.jsonl"
)


def development_module(path=MODULE):
    assert path.is_file(), "The source-bound task-110 graph revision is missing"
    spec = importlib.util.spec_from_file_location("task110_protected_graph", path)
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
def test_historical_control_log_preserves_its_exact_source_revision():
    assert ARTIFACT.is_file(), "The task-110 protected control log is missing"
    report = inspect_oracle_review(ARTIFACT, Path(CACHE))
    assert report["source_digest"] == (
        "0daeaf62640237d5a4af2645c75f4f71a9645c78490781cd30ae79787833b924"
    )
    assert report["source_matches_running_source"] is False
    assert report["file_sha256"] == (
        "b8474eee4ffe0340847e281452918141c0b405b0c4a9d54c73443624bc33e305"
    )
    assert report["control_count"] == report["controls_matching_expectation"] == 18
    assert (report["expected_passes"], report["expected_failures"]) == (6, 12)
    assert not report["unexpected_outcomes"]
    assert report["independent_review"] is False
    assert report["publication_eligible"] is False
    revision_digest = hashlib.sha256((ARTIFACT.parent / "revision.py").read_bytes()).hexdigest()
    events = [json.loads(line)["event"] for line in ARTIFACT.read_bytes().splitlines()]
    header = events[0]
    archived = development_module(ARTIFACT.parent / "revision.py")
    expected_cases = {}
    for suite in ("normal", "hard"):
        source = load_suite(suite, Path(CACHE))[110]
        for probe in archived.probes(source):
            key = f"{suite}/{source.public.task_id}/{probe.name}"
            expected_cases[key] = {
                "task_digest": source.digest,
                "expectation": probe.expectation,
                "rationale": probe.rationale,
                "completion": probe.completion,
            }
    assert header["selection"]["cases"] == expected_cases
    assert len(header["selection"]["declared_judges"]) == 2
    for manifest in header["selection"]["declared_judges"].values():
        assert manifest["revision_file_sha256"] == revision_digest
        assert manifest["source"]["digest"] == report["source_digest"]
        assert manifest["inner"]["protocol"] == "upstream-graph-v4"
        assert manifest["release_eligible"] is False


def synthetic_current_log(tmp_path, revision):
    """Test fixture only: historic transcripts plus newly synthesized terminal messages."""
    from graybench.upstream_evidence import capture_judgment

    records = [json.loads(line) for line in ARTIFACT.read_bytes().splitlines()]
    header = records[0]["event"]
    header["source"] = source_manifest()
    sources = {suite: load_suite(suite, Path(CACHE))[110] for suite in ("normal", "hard")}
    judge = revision.Task110GraphJudge(
        image=header["selection"]["declared_judges"]["normal/qiskitHumanEval/110"]["inner"]["image"]
    )
    declared = {
        f"{suite}/{source.public.task_id}": judge.configuration(source)[1]
        for suite, source in sources.items()
    }
    header["selection"]["declared_judges"] = declared
    for record in records:
        result = record["event"]
        if result["kind"] != "result":
            continue
        manifest = declared[result["task_key"].rsplit("/", 1)[0]]
        judgment = result["evidence"]["judgment"]
        judgment["manifest"] = manifest
        judgment["inner"]["manifest"] = manifest["inner"]
        result["judge_digest"] = identity(manifest)
        fields = {
            key: judgment["inner"][key]
            for key in ("calls", "detail", "exception")
            if key in judgment["inner"]
        }
        message, artifact = capture_judgment(
            (
                json.dumps({"kind": "judgment", "outcome": result["outcome"], "evidence": fields})
                + "\n"
            ).encode(),
            limit=manifest["inner"]["output_limit"],
        )
        judgment["inner"]["trusted_judgment"] = message
        judgment["inner"]["trusted_judgment_artifact"] = artifact
        judgment["inner"]["termination_source"] = "trusted_judgment"
    path = tmp_path / "synthetic-current.jsonl"
    write_rechained(path, records)
    return path, records


def write_rechained(path, records):
    previous = "0" * 64
    for index, record in enumerate(records, 1):
        record["sequence"] = index
        record["previous"] = previous
        record["digest"] = identity(
            {key: value for key, value in record.items() if key != "digest"}
        )
        previous = record["digest"]
    path.write_bytes(b"\n".join(canonical(record) for record in records) + b"\n")


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize(
    "edit",
    [
        None,
        "completion",
        "case",
        "manifest",
        "hash",
        "transcript",
        "outcome",
        "sequence-type",
        "transcript-shape",
        "graph-session",
        "graph-sequence",
        "response-protocol",
    ],
)
def test_exact_control_verifier_rejects_rechained_plan_and_result_edits(tmp_path, edit):
    revision = development_module()
    assert callable(getattr(revision, "verify", None)), "Exact task-110 verifier is missing"
    path, records = synthetic_current_log(tmp_path, revision)
    if edit is None:
        assert revision.verify(Path(CACHE), path)["controls_matching_expectation"] == 18
        return
    header = records[0]["event"]
    result = next(r["event"] for r in records if r["event"]["kind"] == "result")
    key = result["task_key"]
    if edit == "completion":
        header["selection"]["cases"][key]["completion"] = "return []"
        header["tasks"][key] = identity(header["selection"]["cases"][key])
    elif edit == "case":
        del header["selection"]["cases"][key]
        del header["tasks"][key]
        records = [r for r in records if r["event"].get("task_key") != key]
    elif edit == "manifest":
        manifest = result["evidence"]["judgment"]["manifest"]
        manifest["public_contract_digest"] = "0" * 64
        result["judge_digest"] = identity(manifest)
    elif edit == "hash":
        result["evidence"]["judgment"]["inner"]["completion_sha256"] = "0" * 64
    elif edit == "transcript":
        result["evidence"]["judgment"]["inner"]["transcript"][0]["response"] = "0" * 64
    elif edit in {"sequence-type", "transcript-shape"}:
        exchange = result["evidence"]["judgment"]["inner"]["transcript"][0]
        if edit == "sequence-type":
            exchange["call_data"]["sequence"] = True
        else:
            exchange["call_data"] = []
        exchange["call"] = identity(exchange["call_data"])
    elif edit in {"graph-session", "graph-sequence", "response-protocol"}:
        exchange = result["evidence"]["judgment"]["inner"]["transcript"][0]
        if edit == "graph-session":
            exchange["call_data"]["graph"]["session"] = "0" * 32
            exchange["response_data"]["response"]["graph"]["session"] = "f" * 32
        elif edit == "graph-sequence":
            exchange["call_data"]["graph"]["sequence"] = 999
            exchange["response_data"]["response"]["graph"]["sequence"] = 999
        else:
            exchange["response_data"]["response"]["protocol"] = 99
        exchange["call"] = identity(exchange["call_data"])
        exchange["response"] = identity(exchange["response_data"])
    else:
        result["outcome"] = "fail"
        result["evidence"]["matches_expectation"] = False
    write_rechained(path, records)
    with pytest.raises(ValueError):
        revision.verify(Path(CACHE), path)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_exact_verifier_rejects_log_changed_after_chain_inspection(tmp_path, monkeypatch):
    revision = development_module()
    path, records = synthetic_current_log(tmp_path, revision)
    inspect = revision.inspect_oracle_review

    def replace_after_inspection(path, cache):
        report = inspect(path, cache)
        records[0]["event"]["created_at"] = "2000-01-01T00:00:00Z"
        write_rechained(path, records)
        return report

    monkeypatch.setattr(revision, "inspect_oracle_review", replace_after_inspection)
    with pytest.raises(ValueError, match="changed during"):
        revision.verify(Path(CACHE), path)

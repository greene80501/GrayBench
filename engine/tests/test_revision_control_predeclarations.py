"""Control runners must reserve logs using source-bound judge declarations."""

import importlib.util
import json
import os
from pathlib import Path

import pytest

from graybench.datasets import load_suite
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.oracle_review import run_review

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"


def control_runner(number):
    path = (
        Path(__file__).resolve().parents[2]
        / f"docs/reliability-evidence/task{number}_protected_graph.py"
    )
    spec = importlib.util.spec_from_file_location(f"task{number}_controls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, getattr(module, f"Task{number}GraphJudge")(image=IMAGE)


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("number", [50, 108, 117])
def test_control_run_reserves_predeclared_source_and_contract_before_evaluation(
    number, tmp_path, monkeypatch
):
    module, judge = control_runner(number)
    sources = tuple(load_suite(suite, Path(CACHE))[number] for suite in ("normal", "hard"))
    declared = {f"{t.public.suite}/{t.public.task_id}": judge.configuration(t)[1] for t in sources}

    def stop_before_execution(*_args):
        raise RuntimeError("offline reservation reached; no candidate execution")

    monkeypatch.setattr(judge, "evaluate", stop_before_execution)
    output = tmp_path / "reserved.jsonl"
    with pytest.raises(RuntimeError, match="offline reservation reached"):
        run_review(sources, judge, output, probes_for=module.probes, declared_judges=declared)
    header = json.loads(output.read_text().splitlines()[0])["event"]
    assert header["selection"]["declared_judges"] == declared
    for source in sources:
        manifest = declared[f"{source.public.suite}/{source.public.task_id}"]
        assert manifest["source_task_digest"] == source.digest
        assert manifest["public_contract_digest"] == module.revised_task(source).public.digest


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.parametrize("number", [50, 108, 117])
def test_wrapper_evaluation_uses_the_same_manifest_identity(number, monkeypatch):
    _, judge = control_runner(number)
    source = load_suite("normal", Path(CACHE))[number]
    # No isolated execution: exercise the outer binding with an infrastructure result.
    monkeypatch.setattr(
        judge.inner.inner,
        "evaluate",
        lambda *_args: Judgment("infrastructure_error", "0" * 64, {"reason": "offline fixture"}),
    )
    manifest = judge.configuration(source)[1]
    result = judge.evaluate(source, "unused authored fixture")
    assert result.outcome == "infrastructure_error"
    assert result.judge_digest == identity(manifest)
    assert result.evidence["manifest"] == manifest

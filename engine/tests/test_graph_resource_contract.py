"""Resource extensions are explicit and preserve historical default bounds."""

import os
from pathlib import Path

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.circuit_wire import WireError
from graybench.datasets import JudgeTask, load_suite
from graybench.graph_limits import GraphLimits
from graybench.upstream import UpstreamJudge

IMAGE = "sha256:" + "a" * 64


def test_graph_array_budget_is_explicitly_bound_to_payload_and_manifest(task):
    task = JudgeTask(
        public=task,
        canonical_solution="def answer(x): return x+1",
        upstream_test="def check(candidate): pass",
        upstream_difficulty="basic",
    )
    limits = GraphLimits(message_bytes=16 * 1024 * 1024, array_bytes=4 * 1024 * 1024)
    judge = UpstreamJudge(
        image=IMAGE, protocol=4, output_limit=16 * 1024 * 1024, graph_limits=limits
    )
    payload, manifest = judge.configuration(task)
    assert payload["graph_limits"] == manifest["graph_limits"] == limits.record()
    assert GraphLimits.from_record(payload["graph_limits"]) == limits
    old_payload, _ = UpstreamJudge(image=IMAGE, protocol=4).configuration(task)
    assert old_payload["graph_limits"]["array_bytes"] == 524288


def test_graph_limits_cannot_disagree_with_transport_or_downgrade():
    limits = GraphLimits(message_bytes=2 * 1024 * 1024)
    with pytest.raises(ValueError, match="state"):
        UpstreamJudge(image=IMAGE, protocol=4, graph_limits=limits)
    with pytest.raises(ValueError, match="protocol4"):
        UpstreamJudge(image=IMAGE, protocol=3, graph_limits=limits)


@pytest.mark.parametrize("value", [True, 0, -1, 16 * 1024 * 1024 + 1, 1.5])
@pytest.mark.parametrize("field", ["array_bytes", "matrix_bytes"])
def test_extended_storage_budget_still_has_strict_resource_ceiling(value, field):
    with pytest.raises(WireError, match="resource"):
        GraphLimits(**{field: value})


@pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned source cache required"
)
def test_bb84_recipe_records_its_actual_output_default_for_reconstruction(model):
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    source = load_suite("normal", cache)[63]
    setup = build_setup(
        "bb84-resource-binding",
        model,
        (source,),
        IMAGE,
        evaluation_recipe="qhe63-explicit-bases-v2",
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.output_limit == 16 * 1024 * 1024
    assert restored.tasks(cache)[0].public.task_id == "qiskitHumanEval/63"

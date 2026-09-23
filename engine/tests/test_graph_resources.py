"""Configured graph budgets must be frozen and reach both runtime arenas."""

import os
import subprocess
import sys

import pytest
from test_graph_bridge import task

from graybench.circuit_wire import WireError
from graybench.graph_limits import GraphLimits
from graybench.identity import identity
from graybench.upstream import UpstreamJudge

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "0" * 64)
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")


def test_graph_limit_record_is_part_of_private_payload_and_judge_identity():
    item = task("def check(candidate): assert candidate() == 1")
    small = UpstreamJudge(image=IMAGE, protocol=4, output_limit=1048576)
    large = UpstreamJudge(image=IMAGE, protocol=4, output_limit=4194304)
    payload, manifest = large.configuration(item)
    assert payload["graph_limits"] == manifest["graph_limits"]
    assert manifest["graph_limits"] == {
        "nodes": 100000,
        "edges": 100000,
        "message_bytes": 4194304,
        "array_bytes": 524288,
        "matrix_bytes": 524288,
        "depth": 32,
    }
    assert manifest["wire_output_accounting"] == "cumulative-per-process-including-bootstrap-v1"
    assert small.configuration(item)[0]["graph_limits"]["message_bytes"] == 1048576
    assert identity(manifest) != identity(small.configuration(item)[1])


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Immutable image required")
@pytest.mark.parametrize("limit,outcome", [(1048576, "unsupported"), (4194304, "pass")])
def test_configured_large_graph_message_reaches_both_protected_arenas(limit, outcome):
    item = task("""def check(candidate):
    value = 'x' * 1100000
    assert candidate(value) == len(value)
""")
    result = UpstreamJudge(image=IMAGE, docker=DOCKER, protocol=4, output_limit=limit).evaluate(
        item, "def answer(value): return len(value)"
    )
    assert result.outcome == outcome, result.evidence.get("detail")


@pytest.mark.parametrize("fault", ["missing", "extra", "boolean", "over_ceiling"])
def test_malformed_runtime_limit_records_are_rejected(fault):
    record = GraphLimits().record()
    if fault == "missing":
        del record["nodes"]
    elif fault == "extra":
        record["callback"] = "unsafe"
    elif fault == "boolean":
        record["depth"] = True
    else:
        record["message_bytes"] = 16777217
    with pytest.raises(WireError):
        GraphLimits.from_record(record)


def test_host_resource_contract_does_not_import_scientific_or_sdk_modules():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            """import sys
from graybench.graph_limits import GraphLimits
assert GraphLimits().record()['message_bytes'] == 1048576
assert not any(name.split('.')[0] in {'numpy', 'qiskit'} for name in sys.modules)
""",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_delta_transport_and_expanded_capacity_are_frozen_independently():
    item = task("def check(candidate): assert candidate() == 1")
    snapshot = UpstreamJudge(image=IMAGE, protocol=4)
    delta = UpstreamJudge(
        image=IMAGE, protocol=4, graph_transport="delta-v1", graph_state_limit=4194304
    )
    payload, manifest = delta.configuration(item)
    assert (
        payload["graph_transport"]
        == manifest["graph_transport"]
        == {
            "mode": "delta-v1",
            "wire_bytes": 1048576,
            "state_bytes": 4194304,
        }
    )
    assert payload["graph_limits"]["message_bytes"] == 4194304
    assert manifest["output_limit"] == 1048576
    assert identity(manifest) != identity(snapshot.configuration(item)[1])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"protocol": 3, "graph_transport": "delta-v1"},
        {"protocol": 4, "graph_transport": "unknown"},
        {"protocol": 4, "graph_state_limit": True},
        {"protocol": 4, "graph_state_limit": 16777217},
        {"protocol": 4, "graph_state_limit": 4194304},
    ],
)
def test_invalid_or_ineffective_transport_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        UpstreamJudge(image=IMAGE, **kwargs)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Immutable image required")
def test_delta_protected_calls_propagate_retained_mutations_under_wire_budget():
    item = task("""def check(candidate):
    held = [0, ['x' * 20000]]
    assert candidate(held) is held
    for i in range(1, 61):
        assert candidate() == i
        assert held[0] == i
""")
    code = """held = None
def answer(value=None):
    global held
    if value is not None:
        held = value
        return held
    held[0] += 1
    return held[0]
"""
    result = UpstreamJudge(
        image=IMAGE, docker=DOCKER, protocol=4, graph_transport="delta-v1"
    ).evaluate(item, code)
    assert result.outcome == "pass", result.evidence.get("detail")
    assert result.evidence["calls"] == 61

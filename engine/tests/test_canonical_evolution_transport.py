"""Qualification must inspect actual canonical transport, not a SciPy helper flag."""

import importlib.util
import os
from pathlib import Path

import pytest

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")


def probe_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/canonical_evolution_transport.py"
    )
    spec = importlib.util.spec_from_file_location("canonical_transport_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_canonical_probe_records_rust_owner_and_actual_unsupported_transport():
    pytest.importorskip("qiskit")
    report = probe_module().report(Path(CACHE))
    assert len(report["cases"]) == 32
    assert {case["suite"] for case in report["cases"]} == {"normal", "hard"}
    for case in report["cases"]:
        assert case["numerical_outcome"] == "pass"
        assert case["graph_outcome"] == "unsupported"
        assert case["graph_detail"] == "External array buffer requires a graph codec"
        assert case["owner_chain"][-1]["type"] == "PySliceContainer"
        assert case["owner_chain"][-1]["buffer_exported"] is False
    assert report["runtime_qualified"] is False
    assert report["publication_eligible"] is False


def test_probe_does_not_confuse_supported_wrong_action_with_a_valid_control():
    pytest.importorskip("qiskit")
    from qiskit import QuantumCircuit

    probe = probe_module()
    case = probe.probe_case(lambda label, time: QuantumCircuit(len(label)), "X", 1.0)
    assert case["graph_outcome"] == "supported"
    assert case["numerical_outcome"] == "fail"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_canonical_graph_guard_observes_rust_storage_even_with_a_scipy_helper(monkeypatch):
    pytest.importorskip("qiskit")
    from scipy.linalg import _internal_matfuncs

    # A SciPy feature flag cannot qualify an unrelated Qiskit allocation.
    def unrelated_helper(_value):
        raise AssertionError("The Rust owner must not use a SciPy descriptor")

    monkeypatch.setattr(
        _internal_matfuncs, "_graybench_storage_descriptor", unrelated_helper, raising=False
    )
    from test_matrix_semantics_conditions import (
        test_full_retained_graph_roundtrip_preserves_alternatives_and_input_mutation,
    )

    with pytest.raises(pytest.skip.Exception, match="Observed.*PySliceContainer"):
        test_full_retained_graph_roundtrip_preserves_alternatives_and_input_mutation(
            116, "canonical", "normal"
        )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_strict_graph_guard_fails_instead_of_skipping_unsupported_canonical(monkeypatch):
    pytest.importorskip("qiskit")
    monkeypatch.setenv("GRAYBENCH_REQUIRE_CANONICAL_GRAPH", "1")
    from test_matrix_semantics_conditions import (
        test_full_retained_graph_roundtrip_preserves_alternatives_and_input_mutation,
    )

    try:
        with pytest.raises(pytest.fail.Exception, match="canonical.*unsupported"):
            test_full_retained_graph_roundtrip_preserves_alternatives_and_input_mutation(
                116, "canonical", "normal"
            )
    except pytest.skip.Exception as exc:
        raise AssertionError("Strict qualification must fail instead of skipping") from exc


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_strict_qualification_refuses_unsupported_canonical_and_preserves_report(tmp_path):
    pytest.importorskip("qiskit")
    output = tmp_path / "canonical.json"
    with pytest.raises(SystemExit) as error:
        probe_module().main(["--cache", CACHE, "--output", str(output), "--require-supported"])
    assert error.value.code == 1
    import json

    assert json.loads(output.read_text())["runtime_qualified"] is False

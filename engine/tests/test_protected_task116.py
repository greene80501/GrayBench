"""Evolution value scoring must be independent of circuit storage and synthesis."""

import json
import math
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from graybench.datasets import load_suite
from graybench.protected_semantic_judge import ProtectedSemanticJudge, ProtectedSemanticTask
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import (
    ValueExecution,
    ValueRunner,
    parse_value_response,
    value_payload,
)

CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")
IMAGE = "sha256:" + "a" * 64
WORKER = Path(__file__).parents[1] / "src/graybench/protected_value_worker.py"


def pairs(matrix):
    return [[[float(z.real), float(z.imag)] for z in row] for row in matrix]


def check(label, time, value):
    from graybench.evolution_value import check_evolution_matrix

    return check_evolution_matrix(label, time, value)


def source(suite="normal"):
    if not CACHE:
        pytest.skip("Pinned source cache required")
    return load_suite(suite, Path(CACHE))[116]


def test_evolution_accepts_literal_y_rotation_and_retains_identity_global_phase():
    assert check("Y", math.pi / 2, pairs([[0, -1], [1, 0]]))["passed"] is True
    phase = complex(math.cos(0.37), -math.sin(0.37))
    assert check("I", 0.37, pairs([[phase, 0], [0, phase]]))["passed"] is True
    assert check("I", 0.37, pairs([[1, 0], [0, 1]]))["passed"] is False


def test_evolution_oracle_respects_little_endian_tensor_order_and_y_sign():
    xi = pairs([[0, 0, -1j, 0], [0, 0, 0, -1j], [-1j, 0, 0, 0], [0, -1j, 0, 0]])
    yz = pairs([[0, 0, -1, 0], [0, 0, 0, 1], [1, 0, 0, 0], [0, -1, 0, 0]])
    assert check("XI", math.pi / 2, xi)["passed"] is True
    assert check("IX", math.pi / 2, xi)["passed"] is False
    assert check("YZ", math.pi / 2, yz)["passed"] is True
    assert check("ZY", math.pi / 2, yz)["passed"] is False


def test_evolution_tolerance_is_complex_entry_error_without_phase_alignment():
    accepted = pairs([[1, 0], [0, 1]])
    rejected = pairs([[1, 0], [0, 1]])
    accepted[0][1] = [6e-11, 6e-11]
    rejected[0][1] = [8e-11, 8e-11]
    assert check("X", 0, accepted)["passed"] is True
    assert check("X", 0, rejected)["passed"] is False
    assert check("X", 0, pairs([[1j, 0], [0, 1j]]))["passed"] is False


def test_evolution_rejects_finite_entries_whose_complex_error_overflows():
    value = pairs([[1, 0], [0, 1]])
    value[0][0] = [1.7e308, 1.7e308]
    assert check("I", 0, value)["passed"] is False


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), 10**400])
def test_evolution_rejects_nonfinite_bool_and_overflowing_components(bad):
    value = pairs([[1, 0], [0, 1]])
    value[0][0][0] = bad
    assert check("I", 0, value)["passed"] is False


@pytest.mark.parametrize("label,time", [("", 0), ("A", 0), ("IIIIII", 0), ("X", True)])
def test_evolution_rejects_inputs_outside_the_declared_value_domain(label, time):
    assert check(label, time, pairs([[1, 0], [0, 1]]))["passed"] is False


def test_evolution_revision_binds_exact_sources_case_roster_and_value_shapes():
    from graybench.evolution_value import TASK116_ORACLE
    from graybench.protected_task116 import task116_value_task
    from graybench.protected_value_contract import ValueCall

    for suite in ("normal", "hard"):
        pinned = source(suite)
        task = task116_value_task(pinned)
        assert revised_value_task(pinned) == task
        assert revised_value_task(pinned, oracle=TASK116_ORACLE) == task
        assert task.contract.source_task_digest == pinned.digest
        assert task.contract.public.digest != pinned.public.digest
        assert task.contract.public.prompt_format == pinned.public.prompt_format
        assert len(task.cases) == 80
        assert Counter(len(case.call.args[0]) for case in task.cases) == {
            1: 15,
            2: 53,
            3: 2,
            4: 2,
            5: 8,
        }
        assert task.release_eligible is False
        with pytest.raises(ValueError, match="exact pinned"):
            task116_value_task(pinned.model_copy(update={"canonical_solution": "altered"}))
        for cases in (
            task.cases[:-1],
            (task.cases[1], task.cases[0], *task.cases[2:]),
            (
                task.cases[0].model_copy(update={"call": ValueCall(args=("X", 0.11))}),
                *task.cases[1:],
            ),
            (
                task.cases[0].model_copy(update={"call": ValueCall(args=("I", False))}),
                *task.cases[1:],
            ),
        ):
            with pytest.raises(ValidationError, match="full frozen case set"):
                ProtectedSemanticTask(contract=task.contract, oracle=task.oracle, cases=cases)


class TrustedFixtureRunner:
    """Exercise the real worker/parser with authored fixtures only; no isolation claim."""

    def manifest(self, contract):
        return {"scope": "test-only trusted local worker", "contract_digest": contract.digest}

    def execute(self, contract, completion, calls):
        payload = value_payload(contract, completion, calls)
        execution = subprocess.run(
            [sys.executable, str(WORKER)],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert execution.returncode == 0, execution.stderr.decode(errors="replace")
        assert len(execution.stdout) < 1024 * 1024
        try:
            values = parse_value_response(execution.stdout, contract, expected_count=len(calls))
        except ValueError:
            return ValueExecution("candidate_error", (), {"scope": "trusted local fixture"})
        return ValueExecution("returned", values, {"scope": "trusted local fixture"})


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_trusted_worker_controls_accept_canonical_alternatives_and_reject_wrong_values(suite):
    pytest.importorskip("qiskit")
    from graybench.protected_oracle_review import protected_probes

    pinned = source(suite)
    task = revised_value_task(pinned)
    controls = protected_probes(pinned)
    assert Counter(control.expectation for control in controls) == {
        "pass": 3,
        "fail": 10,
        "candidate_error": 2,
    }
    judge = ProtectedSemanticJudge(TrustedFixtureRunner())
    for control in controls:
        result = judge.evaluate(task, pinned, control.completion)
        assert result.outcome == control.expectation, (control.name, result.evidence)
        assert result.evidence["origin_claim"] == "candidate_submitted_value_only"
        assert result.evidence["native_object_attested"] is False
        assert result.evidence["release_eligible"] is False
        if result.outcome in {"pass", "fail"}:
            assert len(result.evidence["case_results"]) == 80


def test_evolution_manifest_binds_both_oracle_and_contract_modules():
    import hashlib

    task = revised_value_task(source())
    manifest = ProtectedSemanticJudge(ValueRunner(image=IMAGE)).manifest(task)
    root = WORKER.parent
    assert (
        manifest["task116_oracle_code_sha256"]
        == hashlib.sha256((root / "evolution_value.py").read_bytes()).hexdigest()
    )
    assert (
        manifest["task116_contract_code_sha256"]
        == hashlib.sha256((root / "protected_task116.py").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_evolution_protected_plan_and_all_adapters_freeze_only_public_contract(suite):
    from graybench.contracts import ModelSpec
    from graybench.protected_campaign import (
        ProtectedCampaignSetup,
        build_protected_setup,
        freeze_protected_cohort,
    )
    from graybench.providers import BUILTINS, adapter

    pinned = source(suite)
    task = revised_value_task(pinned)
    excluded = {
        f"{suite}/qiskitHumanEval/{number}": "unreviewed_or_unsupported"
        for number in range(151)
        if number != 116
    }
    cohort = freeze_protected_cohort(
        (task,),
        cache=Path(CACHE),
        suite=suite,
        image=IMAGE,
        label="evolution value",
        excluded=excluded,
    )
    for name in BUILTINS:
        model = ModelSpec(
            adapter=name,
            model="fixture",
            base_url="http://localhost:11434" if name == "ollama" else "https://example.test/v1",
        )
        setup = build_protected_setup("evolution", model, cohort, (task,), cache=Path(CACHE))
        restored = ProtectedCampaignSetup.model_validate_json(setup.model_dump_json())
        assert restored.tasks == (task,)
        encoded = json.dumps(adapter(name).prepare(model, task.contract.public, None).body)
        assert json.dumps(task.contract.public.prompt)[1:-1] in encoded
        assert json.dumps(pinned.upstream_test)[1:-1] not in encoded
        assert json.dumps(pinned.canonical_solution)[1:-1] not in encoded


def test_cli_predeclares_all_evolution_controls_before_any_execution(tmp_path, monkeypatch):
    from graybench.cli import main

    source()
    output = tmp_path / "evolution-controls.jsonl"

    class BeforeExecution(Exception):
        pass

    def stop(_judge, _task, _source, _completion):
        header = json.loads(output.read_text().splitlines()[0])["event"]
        selection = header["selection"]
        assert Counter(case["expectation"] for case in selection["cases"].values()) == {
            "pass": 6,
            "fail": 20,
            "candidate_error": 4,
        }
        assert len(selection["declared_judges"]) == 2
        for manifest in selection["declared_judges"].values():
            assert len(manifest["case_ids"]) == 80
            assert "task116_oracle_code_sha256" in manifest
            assert "task116_contract_code_sha256" in manifest
            assert manifest["release_eligible"] is False
        raise BeforeExecution

    monkeypatch.setattr(ProtectedSemanticJudge, "evaluate", stop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "graybench",
            "protected-oracle-review",
            CACHE,
            str(output),
            "--suite",
            "both",
            "--image",
            IMAGE,
            "--task",
            "116",
        ],
    )
    with pytest.raises(BeforeExecution):
        main()


@pytest.mark.skipif(
    not CACHE or not os.environ.get("GRAYBENCH_TEST_IMAGE"),
    reason="Pinned cache and image required",
)
def test_isolated_evolution_value_controls_match_declared_outcomes():
    from graybench.protected_oracle_review import protected_probes

    judge = ProtectedSemanticJudge(
        ValueRunner(image=os.environ["GRAYBENCH_TEST_IMAGE"], timeout=30)
    )
    for suite in ("normal", "hard"):
        pinned = source(suite)
        task = revised_value_task(pinned)
        for control in protected_probes(pinned):
            result = judge.evaluate(task, pinned, control.completion)
            assert result.outcome == control.expectation, result.evidence

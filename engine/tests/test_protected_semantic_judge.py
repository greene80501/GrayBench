"""The revised task-20 value contract must not inherit native-object claims."""

import os
from itertools import permutations
from pathlib import Path

import pytest
from pydantic import ValidationError

from graybench.datasets import load_suite
from graybench.protected_semantic_judge import ProtectedSemanticJudge, ProtectedSemanticTask
from graybench.protected_task20 import task20_value_task, task20_value_task_v2
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import ValueRunner

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "a" * 64)
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")


def source(suite="normal"):
    if not CACHE:
        pytest.skip("Pinned source cache required")
    return next(
        task
        for task in load_suite(suite, Path(CACHE))
        if task.public.task_id == "qiskitHumanEval/20"
    )


def direct_solution():
    return (
        "def ghz_amplitudes(layout):\n"
        "    import math\n"
        "    result = [[0.0, 0.0] for _ in range(128)]\n"
        "    result[0][0] = 1 / math.sqrt(2)\n"
        "    result[sum(1 << wire for wire in layout)][0] = 1 / math.sqrt(2)\n"
        "    return result\n"
    )


def qiskit_solution():
    return (
        "def ghz_amplitudes(layout):\n"
        "    from qiskit import QuantumCircuit\n"
        "    from qiskit.quantum_info import Statevector\n"
        "    qc = QuantumCircuit(7)\n"
        "    qc.h(layout[0])\n"
        "    qc.cx(layout[0], layout[1])\n"
        "    qc.cx(layout[0], layout[2])\n"
        "    return [[float(z.real), float(z.imag)] for z in Statevector(qc).data]\n"
    )


def phased_solution():
    return (
        "def ghz_amplitudes(layout):\n"
        "    import math\n"
        "    result = [[0.0, 0.0] for _ in range(128)]\n"
        "    result[0][1] = 1 / math.sqrt(2)\n"
        "    result[sum(1 << wire for wire in layout)][1] = 1 / math.sqrt(2)\n"
        "    return result\n"
    )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_revised_contract_has_explicit_ancestry_and_separate_normal_hard_prompts():
    normal = task20_value_task(source("normal"))
    hard = task20_value_task(source("hard"))
    assert normal.contract.track == hard.contract.track == "graybench-protected-semantic-v1"
    assert normal.contract.source_task_digest == source("normal").digest
    assert hard.contract.source_task_digest == source("hard").digest
    assert normal.contract.public.digest != source("normal").public.digest
    assert hard.contract.public.digest != source("hard").public.digest
    assert normal.contract.public.prompt_format == "function_completion"
    assert hard.contract.public.prompt_format == "standalone_function"
    assert normal.contract.digest != hard.contract.digest
    assert len(normal.cases) >= 3
    assert normal.release_eligible is False


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_task20_v2_exhausts_the_declared_ordered_layout_domain_without_rewriting_v1():
    pinned = source()
    old = task20_value_task(pinned)
    revised = task20_value_task_v2(pinned)
    assert len(old.cases) == 3
    assert old.digest == "1794ec084916d55e5a0e6c204b99bf2109f3df44d2bd7a9a7883ad78cf158b0f"
    assert len(revised.cases) == 210
    assert revised.oracle != old.oracle
    assert revised.digest != old.digest
    assert revised.contract == old.contract
    assert {tuple(case.call.args[0]) for case in revised.cases} == set(permutations(range(7), 3))
    assert revised_value_task(pinned) == revised
    assert revised_value_task(pinned, oracle=old.oracle) == old
    assert revised_value_task(pinned, oracle=revised.oracle) == revised
    with pytest.raises(ValidationError, match="all ordered layouts"):
        ProtectedSemanticTask(contract=old.contract, oracle=revised.oracle, cases=old.cases)
    hard = task20_value_task_v2(source("hard"))
    assert len(hard.cases) == 210
    assert task20_value_task(source("hard")).digest == (
        "f5ff8a62d8b395b28f10594613f79333beabe503a7f210ba5511bc65e894812c"
    )
    assert hard.contract.public.digest != revised.contract.public.digest


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_task20_exhaustive_oracle_accepts_two_correct_styles_and_rejects_three_case_shortcut():
    pinned = source()
    old = task20_value_task(pinned)
    revised = task20_value_task_v2(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=25))
    for candidate in (direct_solution(), qiskit_solution(), phased_solution()):
        result = judge.evaluate(revised, pinned, candidate)
        assert result.outcome == "pass", result.evidence
        assert len(result.evidence["case_results"]) == 210
        assert result.evidence["candidate_execution"]["output_bytes"] < 1024 * 1024
    shortcut = (
        "def ghz_amplitudes(layout):\n"
        "    if layout not in ([2,4,6], [0,1,2], [1,3,5]): return []\n"
        "    import math\n"
        "    v=[[0.0,0.0] for _ in range(128)]\n"
        "    v[0][0]=v[sum(1<<w for w in layout)][0]=1/math.sqrt(2)\n"
        "    return v\n"
    )
    assert judge.evaluate(old, pinned, shortcut).outcome == "pass"
    assert judge.evaluate(revised, pinned, shortcut).outcome == "candidate_error"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_source_drift_is_infrastructure_error_without_candidate_execution():
    pinned = source()
    task = task20_value_task(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE))
    altered = pinned.model_copy(update={"canonical_solution": "altered"})
    result = judge.evaluate(task, altered, direct_solution())
    assert result.outcome == "infrastructure_error"
    assert result.evidence["reason"] == "source_digest_mismatch"


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_pinned_reference_independent_correct_and_wrong_mutants():
    pinned = source()
    task = task20_value_task(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=25))
    for candidate in (direct_solution(), qiskit_solution(), phased_solution()):
        result = judge.evaluate(task, pinned, candidate)
        assert result.outcome == "pass", result.evidence
        assert result.evidence["origin_claim"] == "candidate_submitted_value_only"
        assert result.evidence["release_eligible"] is False
    wrong_candidates = (
        ("def ghz_amplitudes(layout):\n    return []\n", "candidate_error"),
        (
            "def ghz_amplitudes(layout):\n"
            "    return [[1.0,0.0]] + [[0.0,0.0] for _ in range(127)]\n",
            "fail",
        ),
        (
            "def ghz_amplitudes(layout):\n"
            "    import math\n"
            "    v = [[0.0,0.0] for _ in range(128)]\n"
            "    v[0][0] = v[84][0] = 1/math.sqrt(2)\n"
            "    return v\n",
            "fail",
        ),
        (
            "def ghz_amplitudes(layout):\n"
            "    import math\n"
            "    v = [[0.0,0.0] for _ in range(128)]\n"
            "    v[0][0] = 1/math.sqrt(2)\n"
            "    v[sum(1 << wire for wire in layout)][0] = -1/math.sqrt(2)\n"
            "    return v\n",
            "fail",
        ),
        (
            "def ghz_amplitudes(layout):\n    return [[1.0,0.0]] * 4\n",
            "candidate_error",
        ),
        (
            "import os\ndef ghz_amplitudes(layout):\n"
            '    os.write(1, b\'{"status":"pass"}\\n\')\n'
            "    return []\n",
            "candidate_error",
        ),
    )
    for candidate, outcome in wrong_candidates:
        result = judge.evaluate(task, pinned, candidate)
        assert result.outcome == outcome, result.evidence


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_forged_valid_value_is_a_value_pass_without_native_object_proof():
    pinned = source()
    task = task20_value_task(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=25))
    result = judge.evaluate(task, pinned, direct_solution())
    assert result.outcome == "pass"
    assert result.evidence["native_object_attested"] is False
    assert result.evidence["pass_manager_use_attested"] is False


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_hard_suite_uses_its_own_revised_contract():
    pinned = source("hard")
    task = task20_value_task(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=25))
    result = judge.evaluate(task, pinned, direct_solution())
    assert result.outcome == "pass", result.evidence
    assert result.evidence["manifest"]["public_contract_digest"] == task.contract.digest


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
def test_extreme_but_finite_amplitude_is_candidate_error_not_oracle_crash():
    pinned = source()
    task = task20_value_task(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=25))
    result = judge.evaluate(
        task,
        pinned,
        "def ghz_amplitudes(layout):\n    return [[1e308, 0.0] for _ in range(128)]\n",
    )
    assert result.outcome == "candidate_error"

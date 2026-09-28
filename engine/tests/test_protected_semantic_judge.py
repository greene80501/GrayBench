"""The revised task-20 value contract must not inherit native-object claims."""

import os
from pathlib import Path

import pytest

from graybench.datasets import load_suite
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task20 import task20_value_task
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

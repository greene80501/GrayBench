"""Task 2's revised Bell value must be judged without candidate object methods."""

import math
import os
from pathlib import Path

import pytest

from graybench.datasets import load_suite
from graybench.protected_semantic_judge import ProtectedSemanticJudge, _task2_phi_value
from graybench.protected_task2 import task2_value_task
from graybench.protected_value_runner import ValueRunner

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "a" * 64)
CACHE = os.environ.get("GRAYBENCH_TEST_CACHE")


def source(suite="normal"):
    if not CACHE:
        pytest.skip("Pinned source cache required")
    return next(
        task
        for task in load_suite(suite, Path(CACHE))
        if task.public.task_id == "qiskitHumanEval/2"
    )


def direct_solution():
    return (
        "def bell_amplitudes():\n"
        "    import math\n"
        "    a = 1 / math.sqrt(2)\n"
        "    return [[a,0.0],[0.0,0.0],[0.0,0.0],[a,0.0]]\n"
    )


def qiskit_solution():
    return (
        "def bell_amplitudes():\n"
        "    from qiskit import QuantumCircuit\n"
        "    from qiskit.quantum_info import Statevector\n"
        "    circuit = QuantumCircuit(2)\n"
        "    circuit.h(0)\n"
        "    circuit.cx(0, 1)\n"
        "    return [[float(z.real),float(z.imag)] for z in Statevector(circuit).data]\n"
    )


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
def test_normal_and_hard_bind_pinned_source_but_revise_public_value_contract():
    normal = task2_value_task(source("normal"))
    hard = task2_value_task(source("hard"))
    for task, pinned in ((normal, source("normal")), (hard, source("hard"))):
        assert task.contract.source_task_digest == pinned.digest
        assert task.contract.public.digest != pinned.public.digest
        assert task.contract.public.entry_point == "bell_amplitudes"
        assert task.contract.positional == ()
        assert task.contract.result.min_items == task.contract.result.max_items == 4
        assert len(task.cases) == 1
        assert task.release_eligible is False
    assert normal.contract.public.prompt_format == "function_completion"
    assert hard.contract.public.prompt_format == "standalone_function"
    assert normal.contract.digest != hard.contract.digest
    with pytest.raises(ValueError, match="pinned"):
        task2_value_task(source("normal").model_copy(update={"canonical_solution": "altered"}))


def test_host_bell_oracle_accepts_phase_and_tolerance_but_rejects_wrong_states():
    amplitude = 1 / math.sqrt(2)
    bell = [[amplitude, 0.0], [0.0, 0.0], [0.0, 0.0], [amplitude, 0.0]]
    phased = [[0.0, amplitude], [0.0, 0.0], [0.0, 0.0], [0.0, amplitude]]
    near = [[amplitude + 2e-11, 0.0], [0.0, 0.0], [0.0, 0.0], [amplitude, 0.0]]
    for valid in (bell, phased, near):
        assert _task2_phi_value(valid)["passed"] is True
    for wrong in (
        [[amplitude, 0.0], [0.0, 0.0], [0.0, 0.0], [-amplitude, 0.0]],
        [[1.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
        [[0.0, 0.0], [1.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
        [[1.0, 0.0]] * 4,
        [[math.nan, 0.0]] * 4,
    ):
        assert _task2_phi_value(wrong)["passed"] is False


@pytest.mark.skipif(not CACHE, reason="Pinned source cache required")
@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_docker_protected_bell_independent_correct_and_wrong_controls(suite):
    pinned = source(suite)
    task = task2_value_task(pinned)
    judge = ProtectedSemanticJudge(ValueRunner(image=IMAGE, timeout=25))
    phased = (
        "def bell_amplitudes():\n"
        "    import math\n"
        "    a = 1 / math.sqrt(2)\n"
        "    return [[0.0,a],[0.0,0.0],[0.0,0.0],[0.0,a]]\n"
    )
    for candidate in (direct_solution(), qiskit_solution(), phased):
        result = judge.evaluate(task, pinned, candidate)
        assert result.outcome == "pass", result.evidence
        assert result.evidence["native_object_attested"] is False
        assert result.evidence["release_eligible"] is False
    mutants = (
        ("def bell_amplitudes():\n    return []\n", "candidate_error"),
        (
            "def bell_amplitudes():\n"
            "    import math\n"
            "    a=1/math.sqrt(2)\n"
            "    return [[a,0.0],[0.0,0.0],[0.0,0.0],[-a,0.0]]\n",
            "fail",
        ),
        (
            "def bell_amplitudes():\n    return [[1.0,0.0],[0.0,0.0],[0.0,0.0],[0.0,0.0]]\n",
            "fail",
        ),
        (
            "def bell_amplitudes():\n    return [[1e308,0.0],[0.0,0.0],[0.0,0.0],[0.0,0.0]]\n",
            "candidate_error",
        ),
        (
            "import os\ndef bell_amplitudes():\n"
            '    os.write(1,b\'{"status":"pass"}\\n\')\n'
            "    return []\n",
            "candidate_error",
        ),
    )
    for candidate, expected in mutants:
        result = judge.evaluate(task, pinned, candidate)
        assert result.outcome == expected, result.evidence

import os

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import validate_cohort
from graybench.evaluation_recipes import recipe_judge, revised_tasks

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "0" * 64)
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
RECIPES = {
    116: ("qhe116-evolution-semantics-v1", "synthesize_evolution_gate"),
    120: ("qhe120-diagonal-semantics-v1", "create_diagonal_circuit"),
}


def task(family):
    return JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id=f"qiskitHumanEval/{family}",
            family_id=f"qhe/{family}",
            prompt="Return the requested circuit.",
            entry_point=RECIPES[family][1],
            prompt_format="standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="PRIVATE_TEST",
        upstream_difficulty="fixture",
    )


@pytest.mark.parametrize("family", [116, 120])
def test_gate_recipe_binds_public_revision_and_reconstructs(family, model, monkeypatch):
    recipe = RECIPES[family][0]
    original = task(family)
    judge = recipe_judge(recipe, image=IMAGE)
    with pytest.raises(ValueError):
        judge.configuration(original)
    revised = revised_tasks((original,), judge)[0]
    assert revised.public.digest != original.public.digest
    assert revised_tasks((revised,), judge) == (revised,)
    setup = build_setup("gate-semantics", model, (original,), IMAGE, evaluation_recipe=recipe)
    assert setup.protocol.track == "strengthened"
    assert "PRIVATE_" not in setup.model_dump_json()
    monkeypatch.setattr(
        "graybench.campaign_setup.load_suite",
        lambda suite, _: (original,) if suite == "hard" else (),
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.tasks(None) == (revised,)
    validate_cohort(restored.protocol, (revised,), restored.judge())
    with pytest.raises(ValueError):
        judge.revise(task(120 if family == 116 else 116))


EVOLUTION = """from qiskit import QuantumCircuit
from qiskit.circuit.library import HamiltonianGate
from qiskit.quantum_info import Pauli

def synthesize_evolution_gate(pauli_string, time):
    qc = QuantumCircuit(len(pauli_string))
    qc.append(HamiltonianGate(Pauli(pauli_string).to_matrix(), time), range(len(pauli_string)))
    return qc
"""
DIAGONAL = """from qiskit import QuantumCircuit
from qiskit.circuit.library import DiagonalGate

def create_diagonal_circuit(diag):
    n = len(diag).bit_length() - 1
    qc = QuantumCircuit(n)
    qc.append(DiagonalGate(diag), range(n))
    return qc
"""
CASES = [
    (116, "hamiltonian", EVOLUTION, "pass"),
    (116, "negative-time", EVOLUTION.replace("to_matrix(), time", "to_matrix(), -time"), "fail"),
    (116, "half-time", EVOLUTION.replace("to_matrix(), time", "to_matrix(), time / 2"), "fail"),
    (
        116,
        "reversed-order",
        EVOLUTION.replace("Pauli(pauli_string)", "Pauli(pauli_string[::-1])"),
        "fail",
    ),
    (
        116,
        "extra-phase",
        EVOLUTION.replace("    return qc", "    qc.global_phase = 0.2\n    return qc"),
        "fail",
    ),
    (
        116,
        "fixed-example",
        "from qiskit import QuantumCircuit\n"
        "def synthesize_evolution_gate(pauli_string, time):\n"
        "    qc=QuantumCircuit(1)\n    qc.rx(2.0,0)\n    return qc",
        "fail",
    ),
    (120, "diagonal", DIAGONAL, "pass"),
    (
        120,
        "global-phase",
        DIAGONAL.replace("    return qc", "    qc.global_phase = 0.371\n    return qc"),
        "pass",
    ),
    (
        120,
        "conjugate",
        DIAGONAL.replace(
            "DiagonalGate(diag)", "DiagonalGate([complex(v).conjugate() for v in diag])"
        ),
        "fail",
    ),
    (120, "reversed", DIAGONAL.replace("DiagonalGate(diag)", "DiagonalGate(diag[::-1])"), "fail"),
    (
        120,
        "fixed-example",
        DIAGONAL.replace("    n =", "    diag = [1, 1j, -1, -1j]\n    n ="),
        "fail",
    ),
    (120, "wrong-width", DIAGONAL.replace("QuantumCircuit(n)", "QuantumCircuit(n + 1)"), "fail"),
]


for name, scale in (("scaled", "0.5"), ("nonfinite", "float('nan')")):
    code = DIAGONAL.replace(
        "from qiskit.circuit.library import DiagonalGate",
        "import numpy as np\nfrom qiskit.circuit.library import UnitaryGate",
    )
    code = code.replace(
        "DiagonalGate(diag)", "UnitaryGate(np.diag(diag) * " + scale + ", check_input=False)"
    )
    CASES.append((120, name, code, "fail"))


@pytest.mark.parametrize("family", [116, 120])
def test_gate_recipe_rejects_wrong_entry_point(family):
    original = task(family)
    wrong = original.model_copy(
        update={"public": original.public.model_copy(update={"entry_point": "unrelated"})}
    )
    with pytest.raises(ValueError, match="entry point"):
        recipe_judge(RECIPES[family][0], image=IMAGE).revise(wrong)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
@pytest.mark.parametrize("family,name,code,outcome", CASES)
def test_gate_semantics_protected_cases(family, name, code, outcome):
    judge = recipe_judge(RECIPES[family][0], image=IMAGE, docker=DOCKER)
    revised = judge.revise(task(family))
    result = judge.evaluate(revised, code)
    assert result.outcome == outcome, (name, result)
    assert result.evidence["manifest"]["release_eligible"] is False

"""Task-2 development oracle: public type contract and observable amplitudes."""

import os
from math import sqrt

import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.datasets import JudgeTask
from graybench.evaluation_campaign import validate_cohort
from graybench.evaluation_recipes import recipe_judge
from graybench.ledger import StateError

IMAGE = "sha256:" + "0" * 64
RECIPE = "qhe2-bell-statevector-v1"


def task2_fixture(public, suite):
    return JudgeTask(
        public=public.model_copy(
            update={
                "suite": suite,
                "task_id": "qiskitHumanEval/2",
                "family_id": "qhe/2",
                "entry_point": "create_bell_statevector",
                "prompt_format": "function_completion"
                if suite == "normal"
                else "standalone_function",
                "prompt": (
                    "from qiskit.quantum_info import Statevector\n"
                    "def create_bell_statevector() -> Statevector:\n"
                    '    """Return a phi+ Bell statevector."""\n'
                    if suite == "normal"
                    else "Return a phi+ Bell statevector.\n"
                    "Implement create_bell_statevector with no arguments.\n"
                ),
            }
        ),
        canonical_solution="PRIVATE_REFERENCE_SENTINEL",
        upstream_test="def check(candidate):\n    assert candidate().equiv(None)",
        upstream_difficulty="fixture",
    )


def native_result(revised, value):
    namespace = {}
    exec(compile(revised.upstream_test, "task2_revision_test", "exec"), namespace)
    try:
        namespace["check"](lambda: value)
    except AssertionError:
        return "fail"
    return "pass"


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_revised_task2_accepts_equivalent_states_without_candidate_equiv(task, suite):
    original = task2_fixture(task, suite)
    judge = recipe_judge(RECIPE, image=IMAGE)
    revised = judge.revise(original)
    assert "Qiskit Statevector" in revised.public.prompt
    assert original.upstream_test != revised.upstream_test
    assert "PRIVATE_REFERENCE_SENTINEL" not in revised.public.prompt
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    target = Statevector([1 / sqrt(2), 0, 0, 1 / sqrt(2)])
    rounded = Statevector([1 / sqrt(2), 0, 5e-12, 1 / sqrt(2)])
    for value in (target, Statevector.from_instruction(circuit), 1j * target, rounded):
        assert native_result(revised, value) == "pass"


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_revised_task2_rejects_forged_equiv_and_wrong_states(task, suite):
    class Claimed:
        def equiv(self, _other):
            return True

    class Forged(Statevector):
        def equiv(self, _other, rtol=None, atol=None):
            return True

    class ForgedData(Statevector):
        @property
        def data(self):
            return Statevector([1 / sqrt(2), 0, 0, 1 / sqrt(2)]).data

    revised = recipe_judge(RECIPE, image=IMAGE).revise(task2_fixture(task, suite))
    malformed_dims = Statevector([1 / sqrt(2), 0, 0, 1 / sqrt(2)])
    malformed_dims._op_shape._dims_l = Statevector.from_label("01").data
    wrong = (
        Claimed(),
        Forged(Statevector.from_label("01").data),
        ForgedData(Statevector.from_label("01").data),
        Statevector.from_label("00"),
        Statevector([1 / sqrt(2), 0, 0, -1 / sqrt(2)]),
        Statevector([1 / sqrt(2), 0, 0, 1 / sqrt(2)], dims=(4,)),
        Statevector([2 / sqrt(2), 0, 0, 2 / sqrt(2)]),
        Statevector([1 / sqrt(2), 0, 2e-10, 1 / sqrt(2)]),
        Statevector([complex(float("nan"), 0), 0, 0, 1]),
        malformed_dims,
    )
    for value in wrong:
        assert native_result(revised, value) == "fail", type(value).__name__


def test_revised_task2_rejects_mismatched_task_identity(task):
    original = task2_fixture(task, "hard")
    wrong = original.model_copy(
        update={"public": original.public.model_copy(update={"task_id": "qiskitHumanEval/3"})}
    )
    with pytest.raises(ValueError, match="task 2"):
        recipe_judge(RECIPE, image=IMAGE).revise(wrong)


def test_revised_task2_campaign_binds_prompt_and_judge(model, task, monkeypatch):
    originals = tuple(task2_fixture(task, suite) for suite in ("normal", "hard"))
    setup = build_setup("bell-development", model, originals, IMAGE, evaluation_recipe=RECIPE)
    assert setup.protocol.track == "strengthened"
    assert len(setup.protocol.request_digests) == 2
    assert "PRIVATE_REFERENCE_SENTINEL" not in setup.model_dump_json()
    monkeypatch.setattr(
        "graybench.campaign_setup.load_suite",
        lambda suite, _: tuple(t for t in originals if t.public.suite == suite),
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    revised = restored.tasks(None)
    assert len(revised) == 2
    assert all("Qiskit Statevector" in t.public.prompt for t in revised)
    validate_cohort(restored.protocol, revised, restored.judge())
    with pytest.raises((ValueError, StateError)):
        validate_cohort(restored.protocol, originals, restored.judge())


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
@pytest.mark.parametrize("suite", ["normal", "hard"])
@pytest.mark.parametrize(
    "name,completion,expected",
    [
        (
            "circuit-derived",
            "from qiskit import QuantumCircuit\n"
            "from qiskit.quantum_info import Statevector\n"
            "def create_bell_statevector():\n"
            "    qc=QuantumCircuit(2)\n    qc.h(0)\n    qc.cx(0,1)\n"
            "    return Statevector.from_instruction(qc)",
            "pass",
        ),
        (
            "global-phase",
            "from qiskit.quantum_info import Statevector\n"
            "def create_bell_statevector():\n"
            "    return 1j * Statevector([2**-0.5,0,0,2**-0.5])",
            "pass",
        ),
        (
            "phi-minus",
            "from qiskit.quantum_info import Statevector\n"
            "def create_bell_statevector():\n"
            "    return Statevector([2**-0.5,0,0,-2**-0.5])",
            "fail",
        ),
        (
            "forged-equiv",
            "from qiskit.quantum_info import Statevector\n"
            "class Forged(Statevector):\n"
            "    def equiv(self, other, rtol=None, atol=None): return True\n"
            "def create_bell_statevector():\n"
            "    return Forged(Statevector.from_label('01').data)",
            "fail-or-unsupported",
        ),
        (
            "patched-data",
            "import numpy as np\n"
            "from qiskit.quantum_info import Statevector\n"
            "def create_bell_statevector():\n"
            "    wrong=Statevector.from_label('01')\n"
            "    Statevector.data=property(lambda self: np.array([2**-0.5,0,0,2**-0.5]))\n"
            "    return wrong",
            "fail",
        ),
        (
            "patched-dims",
            "from qiskit.quantum_info import Statevector\n"
            "def create_bell_statevector():\n"
            "    wrong=Statevector([2**-0.5,0,0,2**-0.5], dims=(4,))\n"
            "    Statevector.dims=lambda self: (2,2)\n"
            "    return wrong",
            "fail",
        ),
    ],
)
def test_revised_task2_protected_controls(task, suite, name, completion, expected):
    image = os.environ["GRAYBENCH_TEST_IMAGE"]
    judge = recipe_judge(RECIPE, image=image, docker=os.environ.get("GRAYBENCH_DOCKER", "docker"))
    revised = judge.revise(task2_fixture(task, suite))
    result = judge.evaluate(revised, completion)
    if expected == "fail-or-unsupported":
        assert result.outcome in {"fail", "unsupported"}, (name, result)
    else:
        assert result.outcome == expected, (name, result)
    assert result.evidence["manifest"]["release_eligible"] is False

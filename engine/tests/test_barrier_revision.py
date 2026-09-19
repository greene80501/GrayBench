import os

import pytest

from graybench.campaign_setup import build_setup
from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.evaluation_recipes import recipe_judge, revised_tasks

RECIPE = "qhe113-barrier-metrics-v1"
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "0" * 64)
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")


def task():
    return JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="qiskitHumanEval/113",
            family_id="qhe/113",
            prompt=(
                "Remove barriers and return depth_before, depth_after and width in a PropertySet."
            ),
            entry_point="calculate_depth_after_barrier_removal",
            prompt_format="standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="PRIVATE_TEST",
        upstream_difficulty="fixture",
    )


def test_barrier_recipe_requires_public_revision_before_freezing(model):
    original = task()
    judge = recipe_judge(RECIPE, image=IMAGE)
    with pytest.raises(ValueError):
        judge.configuration(original)
    (revised,) = revised_tasks((original,), judge)
    assert revised.public.digest != original.public.digest
    setup = build_setup("barrier", model, (original,), IMAGE, evaluation_recipe=RECIPE)
    assert setup.protocol.track == "strengthened"
    assert "PRIVATE_" not in setup.model_dump_json()
    assert revised_tasks((revised,), judge) == (revised,)


GOOD = """from qiskit.transpiler import PropertySet, PassManager
from qiskit.transpiler.passes import RemoveBarriers
def calculate_depth_after_barrier_removal(qc):
    return PropertySet(depth_before=qc.depth(),
        depth_after=PassManager(RemoveBarriers()).run(qc).depth(), width=qc.width())
"""
MANUAL = """from qiskit.transpiler import PropertySet
def calculate_depth_after_barrier_removal(qc):
    clean = qc.copy_empty_like()
    for item in qc.data:
        if item.operation.name != 'barrier':
            clean.append(item.operation, item.qubits, item.clbits)
    return PropertySet(depth_before=qc.depth(), depth_after=clean.depth(), width=qc.width())
"""


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
@pytest.mark.parametrize(
    "code,outcome",
    [
        (GOOD, "pass"),
        (MANUAL, "pass"),
        (GOOD.replace("return PropertySet(", "return dict("), "fail"),
        (
            "from qiskit.transpiler import PropertySet\n"
            "def calculate_depth_after_barrier_removal(qc):\n"
            "    return PropertySet(depth_before=4,depth_after=4,width=6)",
            "fail",
        ),
        (GOOD.replace("PassManager(RemoveBarriers()).run(qc).depth()", "qc.depth()"), "fail"),
        (GOOD.replace("width=qc.width()", "width=qc.num_qubits"), "fail"),
        (GOOD.replace("width=qc.width()", "width=True"), "fail"),
        (GOOD.replace("width=qc.width()", "width=float(qc.width())"), "fail"),
        (
            GOOD.replace(
                "PassManager(RemoveBarriers()).run(qc).depth()",
                "0",
            ),
            "fail",
        ),
    ],
)
def test_barrier_revision_protected_positive_and_negative_answers(code, outcome):
    judge = recipe_judge(RECIPE, image=IMAGE, docker=DOCKER)
    revised = revised_tasks((task(),), judge)[0]
    result = judge.evaluate(revised, code)
    assert result.outcome == outcome, result
    assert result.evidence["manifest"]["release_eligible"] is False

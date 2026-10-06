"""The task-149 evidence plan names every authored control before execution."""

import importlib.util
import os
import shutil
from collections import Counter
from pathlib import Path

import pytest

from graybench.evaluation_recipes import recipe_judge


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_task149_batch_plan_freezes_all_control_identities():
    script = (
        Path(__file__).resolve().parents[2] / "docs/reliability-evidence/task149_batch_probe.py"
    )
    spec = importlib.util.spec_from_file_location("task149_batch_probe", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    image = "sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd"
    judge = recipe_judge("qhe149-most-common-bitstring-v1", image=image)
    cases, selection = module.plan_cases(
        Path(os.environ["GRAYBENCH_TEST_CACHE"]), judge, image=image
    )

    assert len(cases) == len(selection["cases"]) == 14
    assert set(selection["declared_judges"]) == {
        "normal/qiskitHumanEval/149",
        "hard/qiskitHumanEval/149",
    }
    assert Counter(record["expected"] for record in selection["cases"].values()) == {
        "pass": 4,
        "fail": 8,
        "candidate_error": 2,
    }
    assert {key.split("/", 1)[0] for key in selection["cases"]} == {"normal", "hard"}
    assert all(len(record["completion_sha256"]) == 64 for record in selection["cases"].values())


def test_task149_frozen_plan_verifier_rejects_changed_bytes(tmp_path):
    bundle = (
        Path(__file__).resolve().parents[2]
        / "docs/reliability-evidence/artifacts/task149-batch-controls-2026-10-05"
    )
    spec = importlib.util.spec_from_file_location("task149_control_verifier", bundle / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.verify(bundle)["control_count"] == 14

    changed = tmp_path / "changed"
    changed.mkdir()
    shutil.copyfile(bundle / "plan.json", changed / "plan.json")
    with (changed / "plan.json").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="digest mismatch"):
        module.verify(changed)

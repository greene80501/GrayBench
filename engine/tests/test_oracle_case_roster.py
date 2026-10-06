"""The review roster is exact evidence of calls, not an admission decision."""

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "docs/reliability-evidence/build_oracle_case_roster_2026_10_06.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location("oracle_case_roster", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_roster_matches_current_six_cards_and_exact_private_calls():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    packet = module.build(cache)

    assert module.verify(packet, cache)
    assert packet["publication_eligible"] is False
    assert packet["independent_review"] is False
    assert [len(task["cases"]) for task in packet["tasks"]] == [1, 210, 1364, 1, 210, 1364]
    assert len({case["digest"] for task in packet["tasks"] for case in task["cases"]}) == 1575
    assert all(task["requirements"] for task in packet["tasks"])
    assert all(task["requirement_case_links"] == [] for task in packet["tasks"])


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_roster_rejects_changed_private_case():
    module = load_script()
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    packet = module.build(cache)
    packet["tasks"][0]["cases"][0]["case_id"] = "changed"
    with pytest.raises(ValueError, match="current pinned source"):
        module.verify(packet, cache)

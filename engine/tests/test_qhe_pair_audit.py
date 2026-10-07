import importlib.util
import os
from pathlib import Path

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import KNOWN_FINDINGS, KNOWN_FINDINGS_V2, JudgeTask, load_suite

SCRIPT = Path(__file__).resolve().parents[2] / "docs/reliability-evidence/qhe_pair_audit.py"


@pytest.fixture
def audit():
    spec = importlib.util.spec_from_file_location("qhe_pair_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pair():
    normal = JudgeTask(
        public=PublicTask(
            suite="normal",
            task_id="qiskitHumanEval/0",
            family_id="qhe/0",
            prompt='def answer(x: int):\n    """ Return x.\n    """',
            entry_point="answer",
            prompt_format="function_completion",
        ),
        canonical_solution="\n    return x\n",
        upstream_test="def check(candidate):\n    assert candidate(3) == 3\n",
        upstream_difficulty="basic",
    )
    hard = normal.model_copy(
        update={
            "public": normal.public.model_copy(
                update={
                    "suite": "hard",
                    "prompt_format": "standalone_function",
                    "prompt": "Return x.  \nYou must implement this using a function "
                    "named `answer` "
                    "with the following arguments: x.",
                }
            ),
            "canonical_solution": "def answer(x):\n    return x\n",
            "upstream_test": "from math import sqrt\ndef check(candidate):\n"
            "    assert candidate(3) == 3\n\ncheck(answer)\n",
        }
    )
    return normal, hard


def test_pair_comparison_preserves_information_and_does_not_claim_semantic_proof(audit):
    row = audit.inspect_pair(*pair())
    assert row["requirement_lines_equal"] is True
    assert row["reference_body_ast_equal"] is True
    assert row["check_ast_equal"] is True
    assert row["normal_signature"]["annotations"] == {"x": "int"}
    assert row["hard_declared_arguments"] == ["x"]
    assert row["semantic_adequacy"] == "unreviewed"


def test_wording_change_is_detected_without_rewriting_original_prompt(audit):
    n, h = pair()
    h = h.model_copy(
        update={
            "public": h.public.model_copy(
                update={"prompt": h.public.prompt.replace("Return x.", "Return -x.")}
            )
        }
    )
    row = audit.inspect_pair(n, h)
    assert row["requirement_lines_equal"] is False
    assert row["hard_requirement_lines"] == ["Return -x."]
    assert row["normal_public_digest"] == n.public.digest


@pytest.mark.parametrize(
    "old,new", [("`answer`", "`different`"), ("arguments: x.", "arguments: y.")]
)
def test_wrong_hard_function_contract_is_not_counted_as_equal(audit, old, new):
    n, h = pair()
    h = h.model_copy(
        update={"public": h.public.model_copy(update={"prompt": h.public.prompt.replace(old, new)})}
    )
    with pytest.raises(ValueError, match="hard function declaration"):
        audit.inspect_pair(n, h)


def test_import_movement_is_disclosed_separately_from_changed_assertions(audit):
    n, h = pair()
    n = n.model_copy(
        update={
            "upstream_test": "def check(candidate):\n    from math import sqrt\n"
            "    assert candidate(3) == 3\n"
        }
    )
    row = audit.inspect_pair(n, h)
    assert row["check_ast_equal"] is False
    assert row["check_without_imports_ast_equal"] is True
    h = h.model_copy(update={"upstream_test": h.upstream_test.replace("== 3", "== 4")})
    assert audit.inspect_pair(n, h)["check_without_imports_ast_equal"] is False


def test_changed_reference_body_cannot_be_hidden_by_same_prompt(audit):
    n, h = pair()
    h = h.model_copy(update={"canonical_solution": "def answer(x):\n    return -x\n"})
    assert audit.inspect_pair(n, h)["reference_body_ast_equal"] is False


def test_task41_current_findings_do_not_rewrite_historical_registry():
    assert 41 in KNOWN_FINDINGS
    assert 41 not in KNOWN_FINDINGS_V2
    assert any("XZ" in finding and "YX" in finding for finding in KNOWN_FINDINGS[41])


def test_full_pinned_population_and_task41_authored_controls(audit):
    configured = os.environ.get("GRAYBENCH_TEST_CACHE")
    if not configured:
        pytest.skip("Requires the exact pinned QHE cache")
    cache = Path(configured)
    report = audit.build(cache)
    assert len(report["pairs"]) == 151
    assert report["summary"]["requirement_differences"] == [41]
    assert report["summary"]["check_ast_differences"] == [9, 122]
    assert report["summary"]["check_without_imports_ast_differences"] == []
    assert report["summary"]["reference_body_ast_differences"] == []
    assert report["publication_eligible"] is False
    changed = dict(report, pairs=report["pairs"][:-1])
    with pytest.raises(ValueError, match="exact recreation"):
        audit.verify(changed, cache)
    normal41, hard41 = load_suite("normal", cache)[41], load_suite("hard", cache)[41]
    with pytest.raises(ValueError, match="exact pinned task 41"):
        audit.task41_probe(
            normal41.model_copy(update={"upstream_test": "raise RuntimeError('untrusted')"}), hard41
        )
    probe = audit.task41_probe(load_suite("normal", cache)[41], load_suite("hard", cache)[41])
    assert [(r["pauli"], r["qargs"], r["normal"], r["hard"]) for r in probe["controls"]] == [
        ("YX", [0, 2], "pass", "pass"),
        ("XZ", [0, 2], "fail", "fail"),
        ("YX", [0, 1], "fail", "fail"),
        ("YX", [1, 2], "fail", "fail"),
    ]

"""Task 149's versioned oracle rejects count-order shortcuts."""

import os
from pathlib import Path

import pytest

from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask, load_suite
from graybench.evaluation_recipes import recipe_judge, revised_tasks
from graybench.providers import Ollama

RECIPE = "qhe149-most-common-bitstring-v1"
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "0" * 64)


def task(suite):
    return JudgeTask(
        public=PublicTask(
            suite=suite,
            task_id="qiskitHumanEval/149",
            family_id="qhe/149",
            prompt=(
                "from qiskit.primitives import BitArray\n"
                "def most_common_result(bits: BitArray) -> str:\n"
                '    """Return the most common result."""\n'
                if suite == "normal"
                else "Return the most common bit string using most_common_result(bits)."
            ),
            entry_point="most_common_result",
            prompt_format="function_completion" if suite == "normal" else "standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="def check(candidate):\n    assert candidate is not None\n",
        upstream_difficulty="fixture",
    )


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_task149_revision_freezes_a_separate_public_contract(suite):
    original = task(suite)
    judge = recipe_judge(RECIPE, image=IMAGE)
    with pytest.raises(ValueError, match="Revise"):
        judge.configuration(original)
    (revised,) = revised_tasks((original,), judge)
    assert revised.public.prompt != original.public.prompt
    assert revised.upstream_test != original.upstream_test
    assert revised.canonical_solution == original.canonical_solution
    assert "unique most frequent" in revised.public.prompt
    assert "nonempty" in revised.public.prompt
    assert revised_tasks((revised,), judge) == (revised,)
    payload, manifest = judge.configuration(revised)
    assert payload["test"] == revised.upstream_test
    assert manifest["track"] == RECIPE
    assert manifest["inner"]["protocol"] == "upstream-proxy-v1"
    assert manifest["release_eligible"] is False
    if suite == "normal":
        assert payload["prefix"] == (
            "from statistics import mode\nfrom qiskit.primitives import BitArray\n"
        )


def test_task149_revision_rejects_wrong_family_and_legacy_transport():
    original = task("normal")
    wrong = original.model_copy(
        update={"public": original.public.model_copy(update={"family_id": "qhe/148"})}
    )
    with pytest.raises(ValueError):
        recipe_judge(RECIPE, image=IMAGE).revise(wrong)
    with pytest.raises(ValueError):
        recipe_judge(RECIPE, image=IMAGE, protocol=4)


def test_task149_oracle_accepts_alternative_and_rejects_order_shortcuts():
    pytest.importorskip("qiskit")
    from graybench.task149_revision import CHECK

    namespace = {}
    exec(CHECK, namespace)
    check = namespace["check"]

    def reference(bits):
        from statistics import mode

        return mode(bits.get_bitstrings())

    def alternative(bits):
        counts = bits.get_counts()
        return max(counts, key=counts.get)

    check(reference)
    check(alternative)
    for wrong in (
        lambda bits: bits.get_bitstrings()[0],
        lambda bits: bits.get_bitstrings()[-1],
        lambda bits: "001",
    ):
        with pytest.raises(AssertionError):
            check(wrong)


def test_task149_bitarray_input_survives_protected_value_wire():
    pytest.importorskip("qiskit")
    from qiskit.primitives import BitArray

    from graybench.value_wire import decode, encode

    counts = {"101": 3, "001": 50}
    bits = BitArray.from_counts(counts)
    remote = decode(encode(bits))
    assert remote.get_bitstrings() == bits.get_bitstrings()
    assert remote.get_counts() == bits.get_counts()


def test_task149_campaign_freezes_revised_request(model, monkeypatch):
    original = task("hard")
    setup = build_setup("bitarray", model, (original,), IMAGE, evaluation_recipe=RECIPE)
    key = "hard/qiskitHumanEval/149"
    assert (
        setup.protocol.request_digests[key] != Ollama().prepare(model, original.public, None).digest
    )
    assert "PRIVATE_" not in setup.model_dump_json()
    monkeypatch.setattr(
        "graybench.campaign_setup.load_suite",
        lambda suite, _: (original,) if suite == "hard" else (),
    )
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    (revised,) = restored.tasks(None)
    assert "unique most frequent" in revised.public.prompt


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
def test_pinned_task149_source_digests():
    from graybench.task149_revision import PINNED_SOURCE_TASK_DIGESTS

    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    for suite in ("normal", "hard"):
        original = next(t for t in load_suite(suite, cache) if t.public.family_id == "qhe/149")
        assert original.digest == PINNED_SOURCE_TASK_DIGESTS[suite]


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_pinned_task149_reference_satisfies_revised_oracle(suite):
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    original = next(t for t in load_suite(suite, cache) if t.public.family_id == "qhe/149")
    judge = recipe_judge(RECIPE, image=IMAGE)
    revised = judge.revise(original)
    source = (
        revised.public.prompt + original.canonical_solution
        if suite == "normal"
        else original.canonical_solution
    )
    namespace = {}
    exec(source, namespace)
    exec(revised.upstream_test, namespace)
    namespace["check"](namespace["most_common_result"])


PROTECTED_CONTROLS = (
    ("reference", "__REFERENCE__", "pass"),
    (
        "count-based",
        "    counts = bits.get_counts()\n    return max(counts, key=counts.get)\n",
        "pass",
    ),
    ("first-string", "    return bits.get_bitstrings()[0]\n", "fail"),
    ("last-string", "    return bits.get_bitstrings()[-1]\n", "fail"),
    ("fixed-string", "    return '001'\n", "fail"),
    ("wrong-type", "    return 1\n", "fail"),
    ("candidate-exception", "    raise RuntimeError('deliberate control')\n", "candidate_error"),
)


def control_completion(suite, name, body, original):
    if name == "reference":
        return original.canonical_solution
    if suite == "normal":
        return "\n" + body
    return "from qiskit.primitives import BitArray\n\ndef most_common_result(bits):\n" + body


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_CACHE"), reason="Pinned cache required")
@pytest.mark.parametrize("suite", ["normal", "hard"])
@pytest.mark.parametrize("name,body,expected", PROTECTED_CONTROLS)
def test_task149_predeclared_controls_have_expected_native_outcome(suite, name, body, expected):
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    original = next(t for t in load_suite(suite, cache) if t.public.family_id == "qhe/149")
    revised = recipe_judge(RECIPE, image=IMAGE).revise(original)
    completion = control_completion(suite, name, body, original)
    source = revised.public.prompt + completion if suite == "normal" else completion
    namespace = {}
    exec(source, namespace)
    exec(revised.upstream_test, namespace)
    try:
        namespace["check"](namespace["most_common_result"])
    except AssertionError:
        outcome = "fail"
    except RuntimeError:
        outcome = "candidate_error"
    else:
        outcome = "pass"
    assert outcome == expected, (suite, name)


@pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_CACHE") or not os.environ.get("GRAYBENCH_TEST_IMAGE"),
    reason="Pinned cache and immutable Docker image required",
)
@pytest.mark.parametrize("suite", ["normal", "hard"])
@pytest.mark.parametrize("name,body,expected", PROTECTED_CONTROLS)
def test_task149_protected_controls(suite, name, body, expected):
    cache = Path(os.environ["GRAYBENCH_TEST_CACHE"])
    original = next(t for t in load_suite(suite, cache) if t.public.family_id == "qhe/149")
    judge = recipe_judge(
        RECIPE,
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
    )
    revised = judge.revise(original)
    completion = control_completion(suite, name, body, original)
    result = judge.evaluate(revised, completion)
    assert result.outcome == expected, (suite, name, result)
    assert result.evidence["manifest"]["release_eligible"] is False

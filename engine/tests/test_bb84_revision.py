"""The BB84 development track is a new, publicly specified task."""

import os
from pathlib import Path

import pytest

from graybench.bb84_revision import HARD_REFERENCE, PINNED_SOURCE_TASK_DIGESTS, REFERENCE_BODY
from graybench.campaign_setup import CampaignSetup, build_setup
from graybench.contracts import PublicTask
from graybench.datasets import PINS, JudgeTask, load_suite
from graybench.evaluation_campaign import validate_cohort
from graybench.evaluation_recipes import recipe_judge, revised_tasks
from graybench.ledger import StateError
from graybench.providers import Ollama

RECIPE = "qhe63-explicit-bases-v1"
IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE", "sha256:" + "0" * 64)
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")


def task(suite="normal"):
    return JudgeTask(
        public=PublicTask(
            suite=suite,
            task_id="qiskitHumanEval/63",
            family_id="qhe/63",
            prompt=(
                "from qiskit import QuantumCircuit\n"
                "def bb84_circuit_generate_key(senders_basis, circuit):\n"
                '    """Generate a key using BB84."""\n'
                if suite == "normal"
                else "Generate a BB84 key using senders_basis and circuit."
            ),
            entry_point="bb84_circuit_generate_key",
            prompt_format="function_completion" if suite == "normal" else "standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="def check(candidate):\n    assert candidate is not None\n",
        upstream_difficulty="fixture",
    )


@pytest.mark.parametrize("suite", ["normal", "hard"])
def test_revision_changes_public_signature_and_private_oracle(suite):
    original = task(suite)
    judge = recipe_judge(RECIPE, image=IMAGE)
    with pytest.raises(ValueError, match="Revise"):
        judge.configuration(original)
    (revised,) = revised_tasks((original,), judge)
    assert revised.public.prompt != original.public.prompt
    assert revised.upstream_test != original.upstream_test
    assert revised.canonical_solution != original.canonical_solution
    assert revised.public.prompt.count("receivers_basis") >= 1
    assert "sender" in revised.public.prompt.lower()
    assert "ascending qubit" in revised.public.prompt
    assert "randint" not in revised.public.prompt
    assert "Sampler" not in revised.public.prompt
    assert revised_tasks((revised,), judge) == (revised,)
    payload, manifest = judge.configuration(revised)
    assert payload["test"] == revised.upstream_test
    assert manifest["inner"]["protocol"] == "upstream-graph-v4"
    assert manifest["release_eligible"] is False


def test_normal_full_definition_receives_only_public_imports():
    judge = recipe_judge(RECIPE, image=IMAGE)
    (revised,) = revised_tasks((task(),), judge)
    payload, _ = judge.configuration(revised)
    assert payload["prefix"] == "from qiskit import QuantumCircuit\n"
    assert "PRIVATE_" not in payload["prefix"]


def test_recipe_freezes_revised_request_and_resume(model, monkeypatch):
    original = task("hard")
    setup = build_setup("bb84", model, (original,), IMAGE, evaluation_recipe=RECIPE)
    key = "hard/qiskitHumanEval/63"
    assert setup.protocol.track == "strengthened"
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
    validate_cohort(restored.protocol, (revised,), restored.judge())
    with pytest.raises((StateError, ValueError)):
        validate_cohort(restored.protocol, (original,), restored.judge())


def test_recipe_rejects_wrong_family_and_legacy_bridge():
    original = task()
    wrong = original.model_copy(
        update={"public": original.public.model_copy(update={"family_id": "qhe/62"})}
    )
    with pytest.raises(ValueError):
        recipe_judge(RECIPE, image=IMAGE).revise(wrong)
    with pytest.raises(ValueError):
        recipe_judge(RECIPE, image=IMAGE, protocol=3)
    with pytest.raises(ValueError):
        recipe_judge(RECIPE, image=IMAGE, graph_transport="delta-v1")


def test_pinned_task_source_identity_and_resume_when_cache_is_available(model):
    cache = Path(__file__).resolve().parents[3] / "GrayBench/data/datasets"
    if not all(
        (cache / suite / pin["revision"][:12] / "data/test-00000-of-00001.parquet").exists()
        for suite, pin in PINS.items()
    ):
        pytest.skip("Pinned local dataset cache is unavailable")
    originals = tuple(
        next(t for t in load_suite(suite, cache) if t.public.family_id == "qhe/63")
        for suite in ("normal", "hard")
    )
    for original in originals:
        suite = original.public.suite
        assert original.digest == PINNED_SOURCE_TASK_DIGESTS[suite]
    setup = build_setup("bb84-pinned", model, originals, IMAGE, evaluation_recipe=RECIPE)
    restored = CampaignSetup.model_validate_json(setup.model_dump_json())
    assert restored.tasks(cache) == tuple(restored.judge().revise(t) for t in originals)


STATEVECTOR = """from qiskit.quantum_info import Statevector
def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    measured = circuit.copy()
    for i, basis in enumerate(receivers_basis):
        if basis:
            measured.h(i)
    state = Statevector.from_instruction(measured)
    return ''.join(str(int(state.probabilities([i])[1] > 0.5))
                   for i in range(len(senders_basis))
                   if senders_basis[i] == receivers_basis[i])
"""
FIXED = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    return '1'
"""
BASIS_ONLY = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    return ''.join('0' for a, b in zip(senders_basis, receivers_basis) if a == b)
"""
NO_SIFT = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    return '0' * len(senders_basis)
"""
REVERSE = STATEVECTOR.replace(
    "for i in range(len(senders_basis))", "for i in reversed(range(len(senders_basis)))"
)
ERROR = """def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):
    raise ValueError('candidate fault')
"""


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires immutable image")
@pytest.mark.parametrize("suite", ["normal", "hard"])
@pytest.mark.parametrize(
    "code,outcome",
    [
        ("reference", "pass"),
        (STATEVECTOR, "pass"),
        (FIXED, "fail"),
        (BASIS_ONLY, "fail"),
        (NO_SIFT, "fail"),
        (REVERSE, "fail"),
        (ERROR, "candidate_error"),
    ],
    ids=[
        "simulator-reference",
        "statevector-alternative",
        "fixed-one",
        "basis-only",
        "no-sifting",
        "reverse-order",
        "candidate-exception",
    ],
)
def test_protected_bb84_revision_controls(suite, code, outcome):
    judge = recipe_judge(RECIPE, image=IMAGE, docker=DOCKER)
    (revised,) = revised_tasks((task(suite),), judge)
    completion = (
        (REFERENCE_BODY if suite == "normal" else HARD_REFERENCE) if code == "reference" else code
    )
    result = judge.evaluate(revised, completion)
    assert result.outcome == outcome, result
    assert result.evidence["manifest"]["release_eligible"] is False

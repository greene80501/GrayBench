"""The batch BB84 recipe is distinct and keeps expectations in trusted tests."""

import pytest
from qiskit.quantum_info import Statevector

from graybench.bb84_revision import BB84Judge
from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.evaluation_recipes import recipe_judge
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_delta import DeltaGraphArena
from graybench.graph_limits import GraphLimits
from graybench.graph_wire import GraphArena
from graybench.graph_worker import execute_positional_batch

IMAGE = "sha256:" + "0" * 64


def task(suite):
    return JudgeTask(
        public=PublicTask(
            suite=suite,
            task_id="qiskitHumanEval/63",
            family_id="qhe/63",
            prompt="def bb84_circuit_generate_key(senders_basis, circuit):\n    pass"
            if suite == "normal"
            else "Implement a BB84 key function.",
            entry_point="bb84_circuit_generate_key",
            prompt_format="function_completion" if suite == "normal" else "standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE",
        upstream_test="def check(candidate):\n    assert candidate is not None",
        upstream_difficulty="fixture",
    )


@pytest.mark.parametrize("suite", ("normal", "hard"))
def test_batch_recipe_keeps_v1_prompt_and_freezes_distinct_judge(suite):
    source = task(suite)
    old = BB84Judge(image=IMAGE).revise(source)
    judge = recipe_judge("qhe63-explicit-bases-v2", image=IMAGE)
    revised = judge.revise(source)
    assert revised.public == old.public
    assert revised.upstream_test != old.upstream_test
    payload, manifest = judge.configuration(revised)
    assert payload["graph_batch"] == "positional-batch-v1"
    assert manifest["track"] == "qhe63-explicit-bases-v2"
    assert manifest["inner"]["graph_batch"] == "positional-batch-v1"
    assert manifest["release_eligible"] is False


def test_batch_test_checks_all_588_results_against_independent_statevector():
    source = task("hard")
    judge = recipe_judge("qhe63-explicit-bases-v2", image=IMAGE)
    revised = judge.revise(source)
    namespace = {}
    exec(revised.upstream_test, namespace)
    observed_cases = []

    def batch(cases):
        observed_cases.extend(cases)
        results = []
        for sender, circuit, receiver in cases:
            measured = circuit.copy()
            for index, basis in enumerate(receiver):
                if basis:
                    measured.h(index)
            state = Statevector.from_instruction(measured)
            results.append(
                "".join(
                    str(int(state.probabilities([index])[1] > 0.5))
                    for index in range(len(sender))
                    if sender[index] == receiver[index]
                )
            )
        return tuple(results)

    def candidate(*args, **kwargs):
        raise AssertionError("Batch recipe must not use single calls")

    candidate.batch = batch
    namespace["check"](candidate)
    assert len(observed_cases) == 588
    assert {len(case[0]) for case in observed_cases} == {1, 2, 3, 5, 8}

    candidate.batch = lambda cases: ("wrong",) * len(cases)
    with pytest.raises(AssertionError):
        namespace["check"](candidate)


@pytest.mark.parametrize("implementation", ("copying statevector", "in-place statevector"))
def test_full_batch_roundtrips_through_delta_graph_with_declared_limits(implementation):
    source = task("hard")
    judge = recipe_judge("qhe63-explicit-bases-v2", image=IMAGE)
    revised = judge.revise(source)
    namespace = {}
    exec(revised.upstream_test, namespace)
    registry = PublicAnchorRegistry.capture()
    limits = GraphLimits(message_bytes=16 * 1024 * 1024)
    judge_arena = DeltaGraphArena(
        GraphArena(side="judge", session="task63-local-batch", limits=limits, anchors=registry),
        wire_limit=limits.message_bytes,
    )
    worker_arena = DeltaGraphArena(
        GraphArena(side="candidate", session="task63-local-batch", limits=limits, anchors=registry),
        wire_limit=limits.message_bytes,
    )

    def answer(sender, circuit, receiver):
        measured = circuit.copy() if implementation == "copying statevector" else circuit
        for index, basis in enumerate(receiver):
            if basis:
                measured.h(index)
        state = Statevector.from_instruction(measured)
        return "".join(
            str(int(state.probabilities([index])[1] > 0.5))
            for index in range(len(sender))
            if sender[index] == receiver[index]
        )

    def batch(cases):
        outgoing = judge_arena.snapshot({"args": (cases,), "kwargs": {}}, sequence=1)
        prepared = worker_arena.prepare(outgoing, sequence=1)
        roots = worker_arena.commit(prepared)
        result = execute_positional_batch(answer, roots["args"], roots["kwargs"])
        response = worker_arena.snapshot(
            {**roots, "result": result, "exception_args": None}, sequence=1
        )
        returned = judge_arena.commit(judge_arena.prepare(response, sequence=1))
        return returned["result"]

    def candidate(*args, **kwargs):
        raise AssertionError("Expected a batch call")

    candidate.batch = batch
    namespace["check"](candidate)

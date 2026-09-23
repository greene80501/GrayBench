"""Fault injection must not turn trusted bridge errors into candidate values."""

import os

import pytest

from graybench.contracts import Generation, PublicTask
from graybench.datasets import JudgeTask
from graybench.providers import Ollama
from graybench.upstream import UpstreamJudge

pytestmark = pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires pinned Docker image"
)


@pytest.mark.parametrize(
    "method,error",
    [("snapshot", "RuntimeError"), ("prepare", "OverflowError"), ("commit", "SystemExit")]
    + [
        (method, error)
        for method in ("snapshot", "prepare", "commit")
        for error in ("ValueError", "TypeError")
    ],
)
def test_unexpected_bridge_error_cannot_be_caught_as_passing_candidate(method, error):
    test = f"""from graybench.graph_wire import GraphArena
def broken(self, *args, **kwargs):
    raise {error}("injected trusted bridge failure")
GraphArena.{method} = broken
def check(candidate):
    try:
        candidate([1])
    except BaseException:
        pass
    assert True
"""
    result = evaluate(test, "def answer(value): return value")
    assert result.outcome == "infrastructure_error", result
    assert "injected trusted bridge failure" in result.evidence["detail"]


def evaluate(test, code):
    task = JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="bridge-fault-injection",
            family_id="bridge-fault-injection",
            prompt="Implement answer.",
            entry_point="answer",
            prompt_format="standalone_function",
        ),
        canonical_solution="private reference",
        upstream_test=test,
        upstream_difficulty="fixture",
    )
    return UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
    ).evaluate(task, code)


@pytest.mark.parametrize("error", ["RuntimeError", "ValueError", "TypeError"])
def test_candidate_builtin_error_remains_catchable_and_next_call_runs(error):
    result = evaluate(
        """def check(candidate):
    values = [1]
    try:
        candidate(values)
    except RuntimeError as exc:
        assert exc.args[0] is values
    else:
        assert False
    assert values == [1, 2]
    assert candidate(None) is values
""".replace("RuntimeError", error),
        """saved = None
def answer(values):
    global saved
    if values is None:
        return saved
    saved = values
    values.append(2)
    raise RuntimeError(values)
""".replace("RuntimeError", error),
    )
    assert result.outcome == "pass", result


def test_broken_bridge_exception_diagnostic_still_blocks_judgment():
    result = evaluate(
        """from graybench.graph_wire import GraphArena
class BrokenDiagnostic(Exception):
    def __str__(self):
        raise RuntimeError('diagnostic unavailable')
def broken(self, *args, **kwargs):
    raise BrokenDiagnostic()
GraphArena.commit = broken
def check(candidate):
    try:
        candidate([1])
    except BaseException:
        pass
    assert True
""",
        "def answer(value): return value",
    )
    assert result.outcome == "infrastructure_error", result
    assert "bridge failure" in result.evidence["detail"]


@pytest.mark.parametrize("fault", ["unbound_leaf", "changed_state"])
def test_owner_reconstruction_fault_is_not_scored_as_candidate_error(fault, ledger, protocol, task):
    mutation = (
        "target.append(CircuitInstruction(Gate('unbound', 1, []), target.qubits[:1], []))"
        if fault == "unbound_leaf"
        else "target.global_phase = 0.125"
    )
    result = evaluate(
        f"""from qiskit import QuantumCircuit
from qiskit.circuit import CircuitInstruction, Gate
from graybench.graph_circuit_data import CircuitDataCodec
original = CircuitDataCodec.finalize_owner
def broken(self, target, state, resolve):
    original(self, target, state, resolve)
    if target.num_qubits:
        {mutation}
CircuitDataCodec.finalize_owner = broken
def check(candidate):
    qc = QuantumCircuit(1)
    qc.x(0)
    try:
        candidate(qc)
    except BaseException:
        pass
    assert True
""",
        "def answer(value): return value",
    )
    assert result.outcome == "infrastructure_error", result
    assert "reconstruction" in result.evidence["detail"].lower(), result
    protocol = protocol.model_copy(update={"judge_digest": result.judge_digest})
    run = ledger.create_run(protocol)
    sample = ledger.samples(run)[0]["id"]
    attempt = ledger.begin_attempt(sample, Ollama().prepare(protocol.model, task, None))
    ledger.finish_attempt(
        attempt,
        "returned",
        {},
        200,
        Generation(
            text="def answer(value): return value",
            returned_model="test-model",
            response_id=None,
            finish_reason="stop",
            usage={},
        ),
    )
    ledger.judge(sample, result.judge_digest, result.outcome, result.evidence)
    summary = ledger.summary(run)
    assert summary["complete"] is False
    assert summary["pass_at_1"] is None
    assert summary["outcome_counts"]["candidate_error"] == 0
    assert summary["outcome_counts"]["infrastructure_error"] == 1
    assert "infrastructure_error" in summary["score_blockers"]


def test_outgoing_reconstruction_invariant_failure_is_infrastructure():
    result = evaluate(
        """from graybench.graph_wire import GraphArena
from graybench.graph_owned import GraphReconstructionError
def broken(self, *args, **kwargs):
    raise GraphReconstructionError('injected reconstruction failure')
GraphArena.snapshot = broken
def check(candidate):
    try: candidate([1])
    except BaseException: pass
    assert True
""",
        "def answer(value): return value",
    )
    assert result.outcome == "infrastructure_error", result


def test_valid_late_owner_binding_cannot_be_scored_as_candidate_failure():
    code = """from qiskit import QuantumCircuit
saved = QuantumCircuit(1)
def answer(owner):
    return saved if owner else saved.qubits
"""
    test = """def check(candidate):
    held = candidate(False)
    circuit = candidate(True)
    assert circuit.qubits is held
"""
    namespace = {}
    exec(code, namespace)
    exec(test, namespace)
    namespace["check"](namespace["answer"])
    result = evaluate(test, code)
    # Supporting the alias is the eventual goal. Until then, this valid native
    # behavior must remain unresolved instead of lowering a model's score.
    assert result.outcome in {"pass", "unsupported", "infrastructure_error"}, result

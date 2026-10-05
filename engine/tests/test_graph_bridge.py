"""Actual protected protocol4 regressions; no host graph reconstruction."""

import os

import pytest

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.upstream import UpstreamJudge

IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set immutable GRAYBENCH_TEST_IMAGE")


def task(test):
    return JudgeTask(
        public=PublicTask(
            suite="hard",
            task_id="graph-fixture",
            family_id="graph-fixture",
            prompt="Implement answer.",
            entry_point="answer",
            prompt_format="standalone_function",
        ),
        canonical_solution="PRIVATE_REFERENCE_NOT_FOR_CANDIDATE",
        upstream_test=test,
        upstream_difficulty="fixture",
    )


def judge(test, code):
    return UpstreamJudge(image=IMAGE, docker=DOCKER, protocol=4).evaluate(task(test), code)


def test_opt_in_batch_runs_ordinary_candidate_entry_point_for_each_case():
    result = UpstreamJudge(
        image=IMAGE,
        docker=DOCKER,
        protocol=4,
        graph_batch="positional-batch-v1",
    ).evaluate(
        task("def check(candidate):\n    assert candidate.batch(((1,), (2,), (3,))) == (2, 3, 4)"),
        "def answer(value): return value + 1",
    )
    assert result.outcome == "pass", result
    assert result.evidence["calls"] == 1
    assert result.evidence["manifest"]["graph_batch"] == "positional-batch-v1"


CASES = [
    (
        "same_argument",
        "def answer(a,b): return a is b",
        "def check(candidate):\n    x=[]\n    assert candidate(x,x)",
        "pass",
    ),
    (
        "false_identity_acceptance",
        "def answer(a,b): return a is not b",
        "def check(candidate):\n    x=[]\n    assert candidate(x,x)",
        "fail",
    ),
    (
        "positional_keyword",
        "def answer(a,*,b): return a is b",
        "def check(candidate):\n    x=[]\n    assert candidate(x,b=x)",
        "pass",
    ),
    (
        "returned_input",
        "def answer(a): return a",
        "def check(candidate):\n    x=[]\n    assert candidate(x) is x",
        "pass",
    ),
    (
        "equal_nested_replacement",
        "def answer(a):\n    a[0]=list(a[0])\n    return a",
        "def check(candidate):\n    old=[1]\n    x=[old]\n    assert candidate(x) is x\n"
        "    assert x[0] == old and x[0] is not old",
        "pass",
    ),
    (
        "retained_input",
        "saved=None\ndef answer(a):\n    global saved\n    if a is not None: saved=a\n"
        "    else: saved.append(2)",
        "def check(candidate):\n    x=[1]\n    candidate(x)\n    candidate(None)\n"
        "    assert x == [1,2]",
        "pass",
    ),
]


@pytest.mark.parametrize("name,code,test,expected", CASES, ids=[c[0] for c in CASES])
def test_preserved_native_identity_cases(name, code, test, expected):
    namespace = {}
    exec(code, namespace)
    exec(test, namespace)
    native = "pass"
    try:
        namespace["check"](namespace["answer"])
    except AssertionError:
        native = "fail"
    assert native == expected
    result = judge(test, code)
    assert result.outcome == expected, result
    assert result.evidence["manifest"]["protocol"] == "upstream-graph-v4"
    assert "graph_wire.py" in result.evidence["manifest"]["files"]
    assert result.evidence["candidate_active_seconds"] > 0


def test_mutation_before_caught_exception_and_next_call_survives():
    result = judge(
        """def check(candidate):
    values=[1]
    try:
        candidate(values)
    except ValueError as exc:
        assert exc.args[0] is values
    else:
        assert False
    assert values == [1,2]
    assert candidate(None) is values
""",
        """saved=None
def answer(values):
    global saved
    if values is None: return saved
    saved=values
    values.append(2)
    raise ValueError(values)
""",
    )
    assert result.outcome == "pass", result


def test_actual_protected_circuit_only_singleton_wrapper():
    result = judge(
        """from qiskit import QuantumCircuit
from qiskit.circuit.library import XGate
def check(candidate):
    qc=QuantumCircuit(1)
    qc.x(0)
    assert candidate(qc) is qc
    assert qc.data[0].operation is XGate()
    assert XGate().label == 'candidate mutation'
""",
        """def answer(qc):
    vars(qc.data[0].operation)['_label']='candidate mutation'
    return qc
""",
    )
    assert result.outcome == "pass", result


def test_private_tests_and_reference_not_visible_in_graph_candidate():
    result = judge(
        """def check(candidate):
    files, contents = candidate()
    assert 'task.json' not in files and 'upstream_process.py' not in files
    assert 'upstream_graph_process.py' not in files
    assert 'PRIVATE_REFERENCE_NOT_FOR_CANDIDATE' not in contents
""",
        """from pathlib import Path
def answer():
    root=Path('/input')
    files=[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()]
    return files, '\\n'.join(p.read_text() for p in root.rglob('*.py'))
""",
    )
    assert result.outcome == "pass", result


def test_bootstrap_precedes_candidate_global_singleton_changes():
    result = judge(
        """from qiskit.circuit.library import XGate
def check(candidate):
    result=candidate()
    assert result is XGate() and result.label == 'candidate global'
""",
        """from qiskit.circuit.library import XGate
vars(XGate())['_label']='candidate global'
def answer(): return XGate()
""",
    )
    assert result.outcome == "pass", result


@pytest.mark.parametrize(
    "damage", ["wrong_roots", "wrong_session", "stale_sequence", "extra_field", "wrong_protocol"]
)
def test_malformed_candidate_graph_cannot_be_caught_as_success(damage):
    code = """import inspect, json, os, copy
def answer(*args):
    request=inspect.currentframe().f_back.f_locals['request']
    graph=copy.deepcopy(request['graph'])
    graph['roots'].update(result=True, exception_args=None)
    DAMAGE
    out={'protocol':4,'sequence':request['sequence'],'graph':graph,'exception':None}
    os.write(1,(json.dumps(out)+'\\n').encode())
    return True
""".replace(
        "DAMAGE",
        {
            "wrong_roots": "graph['roots']['args']=None",
            "wrong_session": "graph['session']='forged-session'",
            "stale_sequence": "graph['sequence']=0",
            "extra_field": "graph['verdict']='pass'",
            "wrong_protocol": "pass",
        }[damage],
    )
    if damage == "wrong_protocol":
        code = code.replace("'protocol':4", "'protocol':3")
    result = judge(
        """def check(candidate):
    try: candidate([])
    except BaseException: pass
    assert True
""",
        code,
    )
    assert result.outcome == "candidate_error", result


def test_unknown_exception_metadata_blocks_completeness_even_if_test_catches_everything():
    result = judge(
        """def check(candidate):
    try: candidate()
    except BaseException: pass
    assert True
""",
        """def answer():
    exc=ValueError('custom metadata')
    exc.extra=42
    raise exc
""",
    )
    assert result.outcome == "unsupported", result


def test_graph_calls_keep_container_paused_and_exclude_idle_time():
    import json
    import subprocess
    import time

    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_wire import GraphArena, GraphLimits
    from graybench.sandbox import Candidate

    registry = PublicAnchorRegistry.capture()
    arena = GraphArena(
        side="judge", session="freeze-fixture", limits=GraphLimits(), anchors=registry
    )
    code = """import threading,time
ticks=0
def background():
    global ticks
    while True:
        ticks+=1
        time.sleep(0.01)
threading.Thread(target=background,daemon=True).start()
def answer(): return ticks
"""
    with Candidate(
        code,
        image=IMAGE,
        docker=DOCKER,
        timeout=15,
        protocol=4,
        graph_session="freeze-fixture",
        graph_manifest=registry.manifest(),
    ) as candidate:
        first = candidate.call_graph(
            "answer", arena.snapshot({"args": (), "kwargs": {}}, sequence=1)
        )
        state = json.loads(subprocess.check_output([DOCKER, "inspect", candidate.name]))
        assert state[0]["State"]["Paused"] is True
        used = candidate.active_seconds
        # Exceed the active budget while paused, with enough bootstrap headroom
        # to reach this assertion on a busy Docker host.
        time.sleep(15.2)
        assert candidate.active_seconds == used
        second = candidate.call_graph(
            "answer", arena.snapshot({"args": (), "kwargs": {}}, sequence=2)
        )
        assert second["graph"]["roots"]["result"] - first["graph"]["roots"]["result"] < 100
        assert candidate.active_seconds < candidate.timeout


def test_graph_timeout_cannot_be_caught_as_a_passing_value():
    result = UpstreamJudge(image=IMAGE, docker=DOCKER, protocol=4, candidate_timeout=15).evaluate(
        task("""def check(candidate):
    try: candidate()
    except BaseException: pass
    assert True
"""),
        "def answer():\n    while True: pass",
    )
    assert result.outcome == "timeout", result


def test_normal_function_completion_uses_public_prefix_in_graph_mode():
    item = task("""def check(candidate):
    assert candidate(9) == sqrt(9)
""")
    item = item.model_copy(
        update={
            "public": item.public.model_copy(
                update={
                    "suite": "normal",
                    "prompt_format": "function_completion",
                    "prompt": 'from math import sqrt\ndef answer(x):\n    """Return sqrt."""\n',
                }
            )
        }
    )
    result = UpstreamJudge(image=IMAGE, docker=DOCKER, protocol=4).evaluate(
        item, "    return sqrt(x)\n"
    )
    assert result.outcome == "pass", result


def test_sessions_are_fresh_but_frozen_judge_identity_is_stable():
    test = "def check(candidate):\n    assert candidate(1)==1"
    first = judge(test, "def answer(x): return x")
    second = judge(test, "def answer(x): return x")
    assert first.outcome == second.outcome == "pass"
    assert first.judge_digest == second.judge_digest
    assert first.evidence["graph_session"] != second.evidence["graph_session"]
    for result in (first, second):
        session = result.evidence["graph_session"]
        assert len(session) == 32
        assert result.evidence["transcript"][0]["call_data"]["graph"]["session"] == session
        assert (
            result.evidence["runtime_task_payload_digest"]
            != result.evidence["manifest"]["task_payload"]
        )


def test_graph_discard_result_runs_finalizer_before_state_snapshot():
    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.graph_wire import GraphArena, GraphLimits
    from graybench.sandbox import Candidate

    registry = PublicAnchorRegistry.capture()
    arena = GraphArena(side="judge", session="discard", limits=GraphLimits(), anchors=registry)
    code = """def answer(values):
    class Result:
        def __del__(self): values.append(42)
    return Result()
"""
    with Candidate(
        code,
        image=IMAGE,
        docker=DOCKER,
        protocol=4,
        graph_session="discard",
        graph_manifest=registry.manifest(),
    ) as candidate:
        wire = arena.snapshot({"args": ([],), "kwargs": {}}, sequence=1)
        result = candidate.call_graph("answer", wire, discard_result=True)
        assert result["graph"]["roots"]["result"] is None
        assert any(n["kind"] == "list" and n["state"] == [42] for n in result["graph"]["nodes"])


def test_anchor_bootstrap_mismatch_is_infrastructure_before_candidate_authorization():
    from graybench.graph_anchors import PublicAnchorRegistry
    from graybench.sandbox import Candidate, SandboxInfrastructureError

    manifest = PublicAnchorRegistry.capture().manifest()
    manifest["sha256"] = "0" * 64
    with pytest.raises(SandboxInfrastructureError) as raised:
        Candidate(
            "raise RuntimeError('CANDIDATE_SHOULD_NOT_RUN')",
            image=IMAGE,
            docker=DOCKER,
            protocol=4,
            graph_session="mismatch",
            graph_manifest=manifest,
        )
    assert raised.value.evidence["candidate_authorized"] is False
    assert "CANDIDATE_SHOULD_NOT_RUN" not in raised.value.evidence["observed_stderr"]

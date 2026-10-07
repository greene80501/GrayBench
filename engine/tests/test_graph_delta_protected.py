"""Delta mode must retain the protected snapshot mode's semantic boundaries."""

import os

import pytest
from test_graph_bridge import CASES, task

from graybench.upstream import UpstreamJudge

pytestmark = pytest.mark.skipif(
    not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Requires pinned Docker image"
)


def evaluate(test, code):
    return UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
        graph_transport="delta-v1",
    ).evaluate(task(test), code)


@pytest.mark.parametrize("name,code,test,expected", CASES, ids=[c[0] for c in CASES])
def test_delta_native_identity_cases(name, code, test, expected):
    result = evaluate(test, code)
    assert result.outcome == expected, result.evidence.get("detail")
    assert result.evidence["manifest"]["graph_transport"]["mode"] == "delta-v1"


def test_delta_native_circuit_cache_and_caught_exception_aliases():
    result = evaluate(
        """from qiskit import QuantumCircuit
from qiskit.circuit.library import XGate
def check(candidate):
    qc = QuantumCircuit(1)
    qc.x(0)
    bits = qc.qubits
    try:
        candidate(qc)
    except ValueError as exc:
        assert exc.args[0] is qc
    else:
        assert False
    assert qc.qubits is bits
    assert qc.data[0].operation is XGate()
    assert qc.data[0].operation.label == 'changed'
    assert candidate(None) is qc
""",
        """saved = None
def answer(qc):
    global saved
    if qc is None: return saved
    saved = qc
    vars(qc.data[0].operation)['_label'] = 'changed'
    raise ValueError(qc)
""",
    )
    assert result.outcome == "pass", result.evidence.get("detail")


def test_spoofed_delta_response_cannot_be_caught_as_success():
    result = evaluate(
        """def check(candidate):
    try: candidate([])
    except BaseException: pass
    assert True
""",
        """import copy, inspect, json, os
def answer(values):
    request = inspect.currentframe().f_back.f_locals['request']
    graph = copy.deepcopy(request['graph'])
    graph['side'] = 'candidate'
    graph['roots'].update(result=True, exception_args=None)
    graph['base'] = '0' * 64
    out = {'protocol': 4, 'sequence': request['sequence'], 'graph': graph, 'exception': None}
    os.write(1, (json.dumps(out) + '\\n').encode())
    return True
""",
    )
    assert result.outcome == "candidate_error", result.evidence.get("detail")

import os

import pytest

from graybench.circuit_wire import WireError, decode_circuit, encode_circuit
from graybench.sandbox import Candidate
from graybench.symbolic_wire import decode_parameter, encode_parameter

qc = pytest.importorskip("qiskit.circuit")
qi = pytest.importorskip("qiskit.quantum_info")
np = pytest.importorskip("numpy")


@pytest.mark.parametrize(
    "make",
    [
        lambda a, b: a - b,
        lambda a, b: 2 / (a + 1),
        lambda a, b: 3**a,
        lambda a, b: (a + b) * (a - b),
        lambda a, b: a.sin() + b.cos(),
        lambda a, b: (a + 1) ** 2,
        lambda a, b: (2 - a) / b,
        lambda a, b: a.exp(),
        lambda a, b: a.log(),
        lambda a, b: a.arcsin(),
        lambda a, b: a.arccos(),
        lambda a, b: a.arctan(),
        lambda a, b: a.tan(),
        lambda a, b: a.conjugate(),
    ],
)
def test_symbolic_replay_preserves_bindings(make):
    a, b = qc.Parameter("a"), qc.Parameter("b")
    source = make(a, b)
    result = decode_parameter(encode_parameter(source))
    assert result.parameters == source.parameters
    for av, bv in [(0.2, 0.7), (0.4, 0.6)]:
        bindings = {p: {a: av, b: bv}[p] for p in source.parameters}
        assert complex(result.bind(bindings)) == pytest.approx(complex(source.bind(bindings)))


def test_vector_element_type_uuid_and_positional_binding_order():
    from qiskit.circuit.library import efficient_su2

    source = efficient_su2(3, reps=1)
    result = decode_circuit(encode_circuit(source))
    assert list(result.parameters) == list(source.parameters)
    assert all(isinstance(p, qc.ParameterVectorElement) for p in result.parameters)
    values = np.linspace(-0.9, 1.2, source.num_parameters)
    assert qi.Operator(result.assign_parameters(values)).equiv(
        qi.Operator(source.assign_parameters(values))
    )


def test_same_name_different_uuid_is_not_collapsed():
    first, second = qc.Parameter("theta"), qc.Parameter("theta")
    restored = [decode_parameter(encode_parameter(p)) for p in (first, second)]
    assert restored[0] != restored[1]
    assert restored[0] == first and restored[1] == second


def test_numpy_gate_parameters_keep_type_and_value():
    for source in [np.int64(12), np.float64(0.5), np.complex128(1 + 2j)]:
        result = decode_parameter(encode_parameter(source))
        assert type(result) is type(source)
        assert result == source
    with pytest.raises(WireError):
        encode_parameter(np.float64(float("nan")))


@pytest.mark.parametrize("change", ["opcode", "stack", "vector_size", "uuid", "power"])
def test_malformed_symbolic_records_are_rejected(change):
    p = qc.Parameter("theta")
    if change in {"opcode", "stack", "power"}:
        record = encode_parameter(p + 1)
        if change == "opcode":
            record["program"][0]["op"] = "__import__"
        elif change == "stack":
            record["program"][0]["lhs"] = record["program"][0]["rhs"] = None
        else:
            record = {
                "kind": "expression_v1",
                "program": [{"op": "POW", "lhs": 2, "rhs": 1000000000}],
            }
    else:
        record = encode_parameter(qc.ParameterVector("v", 3)[0])
        if change == "vector_size":
            record["length"] = 10**9
        else:
            record["uuid"] = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(WireError):
        decode_parameter(record)


def test_conflicting_uuid_metadata_is_rejected():
    p = qc.Parameter("a")
    first = encode_parameter(p)
    context = {"parameters": {}, "vectors": {}}
    decode_parameter(first, context)
    second = {**first, "name": "b"}
    with pytest.raises(WireError, match="Conflicting"):
        decode_parameter(second, context)


def test_numeric_replay_cannot_amplify_into_unbounded_integers():
    value = {
        "kind": "expression_v1",
        "program": [
            {"op": "MUL", "lhs": 10**300, "rhs": 10**300},
            {"op": "MUL", "lhs": None, "rhs": 10**300},
        ],
    }
    with pytest.raises(WireError):
        decode_parameter(value)


IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
docker_test = pytest.mark.skipif(not IMAGE, reason="Set immutable GRAYBENCH_TEST_IMAGE")


@docker_test
def test_parameterized_ansatz_crosses_container_boundary():
    from qiskit.circuit.library import efficient_su2

    code = (
        "from qiskit.circuit.library import efficient_su2\n"
        "def answer(): return efficient_su2(3,reps=1,insert_barriers=True)"
    )
    with Candidate(code, image=IMAGE, docker=DOCKER) as candidate:
        returned = candidate.call("answer")
    expected = efficient_su2(3, reps=1, insert_barriers=True)
    values = np.linspace(-0.3, 0.8, returned.num_parameters)
    assert qi.Operator(returned.assign_parameters(values)).equiv(
        qi.Operator(expected.assign_parameters(values))
    )

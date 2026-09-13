import os

import pytest

from graybench.circuit_wire import WireError, decode_circuit, encode_circuit
from graybench.oracles import ghz_custom_layout
from graybench.sandbox import Candidate

QuantumCircuit = pytest.importorskip("qiskit").QuantumCircuit
Operator = pytest.importorskip("qiskit.quantum_info").Operator


def test_numeric_roundtrip_preserves_operator_and_registers():
    source = QuantumCircuit(3, 2)
    source.h(0)
    source.cx(0, 2)
    source.ry(0.43, 1)
    source.rz(-0.2, 2)
    source.global_phase = 0.7
    restored = decode_circuit(encode_circuit(source))
    assert Operator(restored).equiv(Operator(source))
    assert restored == source
    assert [(r.name, len(r)) for r in restored.qregs] == [(r.name, len(r)) for r in source.qregs]
    assert restored.data[0] == source.data[0]
    assert restored.qubits == source.qubits


def test_loose_bits_are_not_invented_as_registered_bits():
    from qiskit.circuit import QuantumRegister, Qubit

    bits = [Qubit(), Qubit()]
    circuit = QuantumCircuit(bits)
    circuit.add_register(QuantumRegister(name="alias", bits=bits))
    restored = decode_circuit(encode_circuit(circuit))
    assert all(bit._register is None for bit in restored.qubits)
    assert restored.qregs[0].name == "alias"


def test_registered_bit_origins_cannot_alias_or_overallocate():
    data = encode_circuit(QuantumCircuit(2))
    data["qubit_origins"][1] = data["qubit_origins"][0]
    with pytest.raises(WireError, match="Duplicate"):
        decode_circuit(data)
    data["qubit_origins"][1] = ["too-large", 1000000000, 0]
    with pytest.raises(WireError):
        decode_circuit(data)


@pytest.mark.parametrize("mutation", ["qubits", "constructor", "arity", "layout", "nan"])
def test_malformed_circuit_rejected_before_execution(mutation):
    source = QuantumCircuit(2)
    source.h(0)
    data = encode_circuit(source)
    if mutation == "qubits":
        data["qubits"] = 10**9
    elif mutation == "constructor":
        data["operations"][0]["name"] = "__import__"
    elif mutation == "arity":
        data["operations"][0]["qubits"] = [0, 1]
    elif mutation == "layout":
        data["layout"] = {"initial": [0, 0], "routing": [0, 1], "input_count": 2}
    else:
        data["phase"] = float("nan")
    with pytest.raises(WireError):
        decode_circuit(data)


def test_symbolic_values_are_explicitly_unsupported():
    from qiskit.circuit import Parameter

    source = QuantumCircuit(1)
    source.rx(Parameter("theta"), 0)
    with pytest.raises(WireError):
        encode_circuit(source)


def test_open_controls_not_silently_changed():
    source = QuantumCircuit(2)
    source.cx(0, 1, ctrl_state=0)
    with pytest.raises(WireError):
        encode_circuit(source)


IMAGE = os.environ.get("GRAYBENCH_TEST_IMAGE")
DOCKER = os.environ.get("GRAYBENCH_DOCKER", "docker")
docker_test = pytest.mark.skipif(not IMAGE, reason="Set immutable GRAYBENCH_TEST_IMAGE")
PREFIX = """from qiskit import QuantumCircuit
from qiskit_ibm_runtime.fake_provider import FakePerth
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
"""


@docker_test
@pytest.mark.parametrize(
    "body,expected",
    [
        ("q.h(0); q.cx(0, [1,2]); q.barrier()", True),
        ("q.h(1); q.cx(1,0); q.cx(1,2); q.global_phase=0.42", True),
        ("pass", False),
        ("q.h([0,1,2])", False),
        ("q.h(0); q.cx(0,1)", False),
        ("q.h(0); q.cx(0,[1,2]); q.z(0)", False),
    ],
)
def test_independent_ghz_oracle_distinguishes_semantics(body, expected):
    source = (
        PREFIX
        + f"""
def answer():
    q=QuantumCircuit(3)
    {body}
    pm=generate_preset_pass_manager(optimization_level=1, backend=FakePerth(),
                                   initial_layout=[2,4,6], seed_transpiler=19)
    return pm.run(q)
"""
    )
    with Candidate(source, image=IMAGE, docker=DOCKER) as worker:
        returned = worker.call("answer")
    # Every mutant satisfies the old oracle, demonstrating why it was insufficient.
    assert returned.num_qubits == 7
    assert returned.layout.initial_index_layout()[:3] == [2, 4, 6]
    evidence = ghz_custom_layout(returned)
    assert evidence["passed"] is expected, evidence


@docker_test
def test_candidate_cannot_supply_its_own_state_fidelity():
    source = "def answer():\n    return {'passed': True, 'state_fidelity': 1.0}"
    with Candidate(source, image=IMAGE, docker=DOCKER) as worker:
        returned = worker.call("answer")
    assert ghz_custom_layout(returned)["passed"] is False


@docker_test
def test_circuit_input_and_mutation_are_observable():
    source = "def answer(q):\n    q.h(0)\n    q.cx(0,1)\n    return len(q.data)"
    original = QuantumCircuit(2)
    with Candidate(source, image=IMAGE, docker=DOCKER) as worker:
        result = worker.call_with_updates("answer", original)
    assert result.value == 2
    assert len(original.data) == 0  # No mutation is silently applied to the trusted input.
    expected = QuantumCircuit(2)
    expected.h(0)
    expected.cx(0, 1)
    assert Operator(result.args_after[0]).equiv(Operator(expected))


@docker_test
def test_read_only_interface_does_not_silently_drop_mutations():
    from graybench.sandbox import UnsupportedInterface

    with Candidate("def answer(q):\n    q.x(0)", image=IMAGE, docker=DOCKER) as worker:
        with pytest.raises(UnsupportedInterface, match="mutation"):
            worker.call("answer", QuantumCircuit(1))

import os

import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import ClassicalRegister, Gate, Instruction

from graybench.circuit_wire import WireError
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_wire import GraphArena, GraphLimits


def arenas():
    registry = PublicAnchorRegistry.capture()
    return tuple(
        GraphArena(
            side=side, session="converted-instructions", limits=GraphLimits(), anchors=registry
        )
        for side in ("judge", "candidate")
    )


def transfer(sender, receiver, value, sequence=1):
    snapshot = sender.snapshot({"value": value}, sequence=sequence)
    return receiver.commit(receiver.prepare(snapshot, sequence=sequence))["value"]


@pytest.mark.parametrize("kind,attribute", [("gate", "condition"), ("instruction", "_condition")])
def test_converter_fields_preserve_actual_dictionary_and_definition(kind, attribute):
    source, target = arenas()
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    operation = circuit.to_gate() if kind == "gate" else circuit.to_instruction()
    assert getattr(operation, attribute) is None
    remote, attrs, definition, params = transfer(
        source, target, (operation, vars(operation), operation.definition, operation.params)
    )
    assert type(remote) is type(operation)
    assert vars(remote) is attrs and remote.definition is definition and remote.params is params
    assert attribute in attrs and attrs[attribute] is None
    assert [item.operation.name for item in definition.data] == ["h", "cx"]
    assert transfer(target, source, remote) is operation


@pytest.mark.parametrize("kind,attribute", [("gate", "condition"), ("instruction", "_condition")])
def test_optional_converter_field_addition_deletion_and_detached_alias(kind, attribute):
    source, target = arenas()
    operation = Gate("g", 1, []) if kind == "gate" else Instruction("i", 1, 0, [])
    remote, attrs = transfer(source, target, (operation, vars(operation)))
    assert attribute not in vars(operation) and attribute not in attrs
    held = [ClassicalRegister(1, "condition_register")[0], 1]
    setattr(operation, attribute, held)
    received, condition = transfer(source, target, (operation, held), sequence=2)
    assert received is remote and vars(remote) is attrs
    assert getattr(remote, attribute) is condition
    delattr(remote, attribute)
    condition.append("detached")
    restored, alias = transfer(target, source, (remote, condition))
    assert restored is operation and alias is held and held[-1] == "detached"
    assert attribute not in vars(operation)
    setattr(operation, attribute, None)
    assert transfer(source, target, operation, sequence=3) is remote
    assert attribute in attrs and getattr(remote, attribute) is None


@pytest.mark.parametrize("kind,attribute", [("gate", "_condition"), ("instruction", "condition")])
def test_converter_support_does_not_accept_other_instance_fields(kind, attribute):
    source, _ = arenas()
    operation = Gate("g", 1, []) if kind == "gate" else Instruction("i", 1, 0, [])
    setattr(operation, attribute, None)
    with pytest.raises(WireError, match="instruction fields"):
        source.snapshot({"value": operation}, sequence=1)


@pytest.mark.parametrize("kind,attribute", [("gate", "condition"), ("instruction", "_condition")])
def test_optional_field_must_agree_with_actual_attribute_dictionary(kind, attribute):
    source, target = arenas()
    operation = (
        Gate("g", 1, [], label="before")
        if kind == "gate"
        else Instruction("i", 1, 0, [], label="before")
    )
    remote = transfer(source, target, operation)
    operation.label = "after"
    snapshot = source.snapshot({"value": operation}, sequence=2)
    record = next(row for row in snapshot["nodes"] if row["kind"] == "python_instruction")
    record["state"][attribute] = None
    with pytest.raises(WireError):
        target.prepare(snapshot, sequence=2)
    assert remote.label == "before" and attribute not in vars(remote)


@pytest.mark.skipif(not os.environ.get("GRAYBENCH_TEST_IMAGE"), reason="Pinned image required")
@pytest.mark.parametrize("transport", ["snapshot-v1", "delta-v1"])
@pytest.mark.parametrize("drop_field", [False, True])
def test_protected_converter_metadata_is_preserved_without_inventing_fields(transport, drop_field):
    from test_graph_bridge import task

    from graybench.upstream import UpstreamJudge

    check = """def check(candidate):
    operation, attrs, definition = candidate()
    assert vars(operation) is attrs and operation.definition is definition
    assert 'condition' in attrs and operation.condition is None
    attrs['condition'] = [17]
    returned = candidate(operation)
    assert returned is operation and returned.condition is attrs['condition']
    assert operation.condition == [17, 23]
"""
    code = """from qiskit import QuantumCircuit
held = None
def answer(operation=None):
    global held
    if operation is not None:
        assert operation is held
        operation.condition.append(23)
        return operation
    circuit = QuantumCircuit(1)
    circuit.h(0)
    held = circuit.to_gate()
    DROP_FIELD
    return held, vars(held), held.definition
""".replace("DROP_FIELD", "del held.condition" if drop_field else "pass")
    result = UpstreamJudge(
        image=os.environ["GRAYBENCH_TEST_IMAGE"],
        docker=os.environ.get("GRAYBENCH_DOCKER", "docker"),
        protocol=4,
        graph_transport=transport,
    ).evaluate(task(check), code)
    assert result.outcome == ("fail" if drop_field else "pass"), result.evidence.get("detail")

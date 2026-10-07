"""Development-only, exact-source QHE task-50 circuit editing condition."""

from graybench.datasets import JudgeTask
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

TRACK = "qhe50-remove-position-graph-v1"
SOURCE_DIGESTS = {
    "normal": "60f869c76c8b50b8f14e7f10ff04d03bfe202353226626f6ebf74b561204f834",
    "hard": "496a2be33bd85417d3d97cab445172e0e6b1e8a7ebce199356d85150e93b8ae0",
}
REQUIREMENT = (
    "Given a nonempty Qiskit QuantumCircuit and an integer position satisfying "
    "0 <= position < the number of instructions, return a QuantumCircuit with "
    "exactly the instruction at that zero-based position removed. Preserve all "
    "other instructions in their original order, including operation types, names, dimensions, "
    "finite operation definitions, "
    "parameters and quantum/classical wire assignments. Numeric parameters are "
    "preserved exactly, with no numerical tolerance. Preserve the qubits, "
    "classical bits, bit and register types, register names, sizes and wire memberships, "
    "and global phase. Instructions may "
    "include gates, barriers, resets and measurements. You may modify the input "
    "or return a separate circuit. Circuit name, metadata and instruction labels "
    "are not scored; native object identity and construction methods are not attested."
)
CHECK = """def check(candidate):
    from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

    solo = QuantumCircuit(1)
    solo.x(0)
    duplicate = QuantumCircuit(1)
    duplicate.x(0)
    duplicate.x(0)
    source = QuantumCircuit(2)
    source.h(0)
    source.cx(0, 1)
    source.h(1)
    source.h(0)
    rotations = QuantumCircuit(2, global_phase=0.375)
    rotations.rx(0.19, 1)
    rotations.ry(-0.41, 0)
    rotations.cx(1, 0)
    rotations.rz(1.17, 1)
    rotations.sx(0)
    left = QuantumRegister(1, 'left')
    right = QuantumRegister(2, 'right')
    readout = ClassicalRegister(1, 'readout')
    registered = QuantumCircuit(left, right, readout, global_phase=0.625)
    registered.h(left[0])
    registered.cx(left[0], right[1])
    registered.rzz(0.23, right[0], right[1])
    registered.barrier()
    registered.measure(right[1], readout[0])
    registered.x(right[0])
    mixed = QuantumCircuit(3, 3, global_phase=0.875)
    mixed.s(2)
    mixed.cx(2, 0)
    mixed.reset(1)
    mixed.ry(0.31, 0)
    mixed.barrier(1, 2)
    mixed.measure(0, 2)
    mixed.cz(0, 2)

    def registers(circuit):
        return (
            tuple((type(r), r.name, len(r), tuple(circuit.find_bit(b).index for b in r))
                  for r in circuit.qregs),
            tuple((type(r), r.name, len(r), tuple(circuit.find_bit(b).index for b in r))
                  for r in circuit.cregs),
        )

    def definition(operation, depth):
        assert depth < 16, 'Invalid recursive operation definition'
        circuit = operation.to_mutable().definition
        if circuit is None:
            return None
        return (circuit.num_qubits, circuit.num_clbits, registers(circuit),
                tuple(type(b) for b in circuit.qubits), tuple(type(b) for b in circuit.clbits),
                circuit.global_phase, instructions(circuit, depth + 1))

    def instructions(circuit, depth=0):
        return tuple(
            (item.operation, item.operation.base_class, item.operation.name,
             item.operation.num_qubits, item.operation.num_clbits,
             tuple(item.operation.params), definition(item.operation, depth),
             tuple(circuit.find_bit(q).index for q in item.qubits),
             tuple(circuit.find_bit(c).index for c in item.clbits))
            for item in circuit.data
        )

    for template in (solo, duplicate, source, rotations, registered, mixed):
        for position in range(len(template.data)):
            supplied = template.copy()
            expected = template.copy_empty_like()
            for index, instruction in enumerate(template.data):
                if index != position:
                    expected.append(instruction.operation, instruction.qubits, instruction.clbits)
            # Freeze before dispatch: mutation of the supplied circuit is permitted.
            wanted_registers = registers(expected)
            wanted_instructions = instructions(expected)
            wanted_phase = expected.global_phase
            wanted_bit_types = (tuple(type(b) for b in expected.qubits),
                                tuple(type(b) for b in expected.clbits))
            actual = candidate(supplied, position)
            assert isinstance(actual, QuantumCircuit), 'Expected a QuantumCircuit'
            assert actual.num_qubits == expected.num_qubits, 'Changed qubit count'
            assert actual.num_clbits == expected.num_clbits, 'Changed classical bit count'
            assert registers(actual) == wanted_registers, 'Changed register definitions'
            assert (tuple(type(b) for b in actual.qubits),
                    tuple(type(b) for b in actual.clbits)) == wanted_bit_types, 'Changed bit types'
            assert actual.global_phase == wanted_phase, 'Changed global phase'
            assert instructions(actual) == wanted_instructions, 'Incorrect ordered instructions'
"""


PINNED_PROMPTS = {
    "normal": (
        "from qiskit import  QuantumCircuit\n"
        "def remove_gate_in_position(circuit: QuantumCircuit, position: int):\n"
        '    """ Remove the gate in the input position for the given Quantum Circuit.\n    """'
    ),
    "hard": (
        "Remove the gate in the input position for the given Quantum Circuit.\n"
        "You must implement this using a function named `remove_gate_in_position` "
        "with the following arguments: circuit, position."
    ),
}
PINNED_CHECK = """def check(candidate):
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    expected_qc = QuantumCircuit(2)
    expected_qc.cx(0, 1)
    expected_qc.h(1)
    expected_qc.h(0)
    assert candidate(qc, 0)==expected_qc, f"Expected {expected_qc}, got {candidate(qc, 0)}"
"""


def revised_task(task: JudgeTask) -> JudgeTask:
    suite = task.public.suite
    if suite not in SOURCE_DIGESTS:
        raise ValueError("Expected the exact pinned QHE task-50 source")
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": PINNED_PROMPTS[suite]}),
            "upstream_test": PINNED_CHECK
            if suite == "normal"
            else (
                "from qiskit import QuantumCircuit\n"
                + PINNED_CHECK
                + "\ncheck(remove_gate_in_position)"
            ),
        }
    )
    if source.digest != SOURCE_DIGESTS[suite]:
        raise ValueError("Expected the exact pinned QHE task-50 source")
    prompt = (
        "from qiskit import QuantumCircuit\n"
        "def remove_gate_in_position(circuit: QuantumCircuit, position: int):\n"
        + '    """'
        + REQUIREMENT
        + '"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement remove_gate_in_position(circuit, position) in Python."
    )
    revised = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": CHECK,
        }
    )
    if task.digest not in (source.digest, revised.digest):
        raise ValueError("Expected the exact pinned QHE task-50 source or its exact revision")
    return revised


class RemoveInstructionJudge:
    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("Task 50 revision requires graph protocol 4")
        if kwargs.pop("graph_transport", "snapshot-v1") != "snapshot-v1":
            raise ValueError("Task 50 revision requires snapshot graph transport")
        if kwargs.pop("graph_batch", "none") != "none":
            raise ValueError("Task 50 revision requires individual calls")
        self.inner = UpstreamJudge(protocol=4, graph_transport="snapshot-v1", **kwargs)

    def revise(self, task):
        return revised_task(task)

    def configuration(self, task):
        if task.digest != revised_task(task).digest:
            raise ValueError("Revise task 50 before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": TRACK,
            "release_eligible": False,
            "source": source_manifest(),
            "pinned_source_task_digest": SOURCE_DIGESTS[task.public.suite],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract": REQUIREMENT,
            "input_mutation": "permitted; copied results also accepted",
            "inner": inner,
            "limitations": [
                "25 authored inputs are not an exhaustive circuit-domain proof",
                "Graph output cannot attest native object provenance or construction methods",
                "Independent task admission and isolated control verification are pending",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome,
            identity(manifest),
            {
                "manifest": manifest,
                "inner": result.evidence,
            },
        )

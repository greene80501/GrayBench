"""Explicit-bases BB84 development task, separate from the pinned upstream oracle."""

from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

RECIPE = "qhe63-explicit-bases-v1"
ENTRY = "bb84_circuit_generate_key"
PINNED_SOURCE_TASK_DIGESTS = {
    "normal": "2ba17e13c1e97e2ad2b96ed3de9589a31f28f3a75553d1b2651e34abb5715ce1",
    "hard": "c456c4772f149f8f88a28f473c4b3b7278490b820847a5dc4327246ec5d8c4af",
}
PUBLIC_CONTRACT = (
    "Inputs are equal-length binary sequences senders_basis and receivers_basis, "
    "and an unmeasured n-qubit QuantumCircuit circuit, with n >= 1. "
    "The circuit prepares independent ideal BB84 states: sender bit 0 or 1 "
    "is encoded in the sender's Z basis (0) or X basis (1) on each qubit. "
    "Return a Python string of the measured bits at positions where sender and "
    "receiver bases match, in ascending qubit-index order; discard all other "
    "positions. For these ideal inputs the retained bits are deterministic. "
    "Use the supplied receivers_basis; do not choose receiver bases."
)
NORMAL_PROMPT = (
    "from qiskit import QuantumCircuit\n"
    "def bb84_circuit_generate_key(senders_basis: list[int], circuit: QuantumCircuit, "
    "receivers_basis: list[int]) -> str:\n"
    f'    """{PUBLIC_CONTRACT}"""\n'
)
HARD_PROMPT = (
    "Implement a function named bb84_circuit_generate_key with arguments "
    "(senders_basis, circuit, receivers_basis) in that order. " + PUBLIC_CONTRACT
)
REFERENCE_BODY = """
    from qiskit_aer import AerSimulator
    receiver_circuit = circuit.copy()
    for qubit, basis in enumerate(receivers_basis):
        if basis:
            receiver_circuit.h(qubit)
    receiver_circuit.measure_all()
    counts = AerSimulator().run(receiver_circuit, shots=1).result().get_counts()
    ascending_bits = next(iter(counts)).replace(' ', '')[::-1]
    return ''.join(ascending_bits[i] for i in range(len(senders_basis))
                   if senders_basis[i] == receivers_basis[i])
"""
HARD_REFERENCE = (
    "from qiskit import QuantumCircuit\n"
    "def bb84_circuit_generate_key(senders_basis, circuit, receivers_basis):\n" + REFERENCE_BODY
)
BB84_CHECK = """def check(candidate):
    from qiskit import QuantumCircuit
    # Bases and bits are independent authored fixtures. Expected keys are derived
    # classically, never by invoking the candidate or a simulator reference.
    cases = (
        ((0,), (0,), (0,), False),
        ((0,), (0,), (1,), False),
        ((0,), (1,), (1,), False),
        ((0, 1), (0, 1), (1, 0), False),
        ((0, 1), (0, 1), (0, 1), False),
        ((1, 0, 0, 1, 1), (0, 1, 1, 1, 0), (0, 0, 0, 1, 1), False),
        ((1, 0, 1, 0, 0), (1, 1, 1, 1, 0), (1, 1, 0, 0, 1), False),
        ((0, 1, 0, 1, 0, 1, 0, 1), (0, 0, 0, 1, 1, 1, 0, 1),
         (1, 1, 0, 0, 1, 0, 1, 0), False),
        ((1, 0, 1), (1, 0, 1), (1, 0, 0), True),
    )
    for sender, receiver, bits, equivalent_x in cases:
        circuit = QuantumCircuit(len(bits))
        for i, bit in enumerate(bits):
            if bit:
                if equivalent_x and i == 0:
                    circuit.h(i)
                    circuit.z(i)
                    circuit.h(i)
                else:
                    circuit.x(i)
            if sender[i]:
                circuit.h(i)
        expected = ''.join(str(bits[i]) for i in range(len(bits))
                           if sender[i] == receiver[i])
        result = candidate(list(sender), circuit, list(receiver))
        assert type(result) is str, 'Expected a Python string'
        assert result == expected, 'Incorrect sifted key'
"""


class BB84Judge:
    """Versioned deterministic task; the original public task remains unchanged."""

    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("BB84 revision requires graph protocol 4")
        if kwargs.pop("graph_transport", "snapshot-v1") != "snapshot-v1":
            raise ValueError("BB84 revision requires snapshot graph transport")
        self.inner = UpstreamJudge(protocol=4, graph_transport="snapshot-v1", **kwargs)

    def revise(self, task):
        if (
            task.public.family_id != "qhe/63"
            or task.public.task_id != "qiskitHumanEval/63"
            or task.public.entry_point != ENTRY
            or (task.public.suite == "normal")
            != (task.public.prompt_format == "function_completion")
        ):
            raise ValueError("BB84 revision requires the matching task 63 family and format")
        prompt = NORMAL_PROMPT if task.public.suite == "normal" else HARD_PROMPT
        reference = REFERENCE_BODY if task.public.suite == "normal" else HARD_REFERENCE
        return task.model_copy(
            update={
                "public": task.public.model_copy(update={"prompt": prompt}),
                "canonical_solution": reference,
                "upstream_test": BB84_CHECK,
            }
        )

    def configuration(self, task):
        revised = self.revise(task)
        if task.digest != revised.digest:
            raise ValueError("Revise the task before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": RECIPE,
            "source": source_manifest(),
            "pinned_source_task_digest": PINNED_SOURCE_TASK_DIGESTS[task.public.suite],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract": PUBLIC_CONTRACT,
            "domain": "Ideal independent BB84 preparations with explicit binary bases, n >= 1",
            "inner": inner,
            "release_eligible": False,
            "limitations": [
                "Nine fixed authored cases are not exhaustive or independently certified",
                "Noisy, measured, malformed and entangled input circuits are out of scope",
                "Graph transport and Qiskit runtime still require separate validation",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

"""Development-only BB84 condition with a benchmark-owned protected batch."""

from graybench.bb84_revision import PINNED_SOURCE_TASK_DIGESTS, PUBLIC_CONTRACT, BB84Judge
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

RECIPE = "qhe63-explicit-bases-v2"
BATCH_CHECK = """def check(candidate):
    from itertools import product
    from qiskit import QuantumCircuit

    cases, expected = [], []

    def add_case(sender, receiver, bits, equivalent_x=False):
        circuit = QuantumCircuit(len(bits))
        for index, bit in enumerate(bits):
            if bit:
                if equivalent_x and index == 0:
                    circuit.h(index)
                    circuit.z(index)
                    circuit.h(index)
                else:
                    circuit.x(index)
            if sender[index]:
                circuit.h(index)
        cases.append((list(sender), circuit, list(receiver)))
        expected.append(''.join(str(bits[index]) for index in range(len(bits))
                                if sender[index] == receiver[index]))

    for width in range(1, 4):
        vectors = tuple(product((0, 1), repeat=width))
        for sender in vectors:
            for receiver in vectors:
                for bits in vectors:
                    add_case(sender, receiver, bits)

    extra = (
        ((1, 0, 0, 1, 1), (0, 1, 1, 1, 0), (0, 0, 0, 1, 1), False),
        ((1, 0, 1, 0, 0), (1, 1, 1, 1, 0), (1, 1, 0, 0, 1), False),
        ((0, 1, 0, 1, 0, 1, 0, 1), (0, 0, 0, 1, 1, 1, 0, 1),
         (1, 1, 0, 0, 1, 0, 1, 0), False),
        ((1, 0, 1), (1, 0, 1), (1, 0, 0), True),
    )
    for sender, receiver, bits, equivalent_x in extra:
        add_case(sender, receiver, bits, equivalent_x)

    assert len(cases) == 588
    observed = candidate.batch(tuple(cases))
    assert type(observed) is tuple and len(observed) == len(expected), 'Wrong result count'
    for index, (actual, correct) in enumerate(zip(observed, expected, strict=True)):
        assert type(actual) is str, f'Expected a Python string at {index}'
        assert actual == correct, f'Incorrect sifted key at {index}'
"""


class BB84BatchJudge(BB84Judge):
    """Separate condition; candidate source remains the ordinary BB84 function."""

    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("BB84 batch revision requires graph protocol 4")
        if kwargs.pop("graph_transport", "delta-v1") != "delta-v1":
            raise ValueError("BB84 batch revision requires delta graph transport")
        if kwargs.pop("graph_batch", "positional-batch-v1") != "positional-batch-v1":
            raise ValueError("BB84 batch revision requires positional batch transport")
        kwargs.setdefault("output_limit", 16 * 1024 * 1024)
        self.inner = UpstreamJudge(
            protocol=4,
            graph_transport="delta-v1",
            graph_batch="positional-batch-v1",
            **kwargs,
        )

    def revise(self, task):
        revised = super().revise(task)
        return revised.model_copy(update={"upstream_test": BATCH_CHECK})

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
                "588 authored cases do not cover unbounded width or have independent review",
                "Batch semantics differ from repeated individual graph exchanges",
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

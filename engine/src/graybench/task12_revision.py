"""Source-bound explicit Bell preparation operator; separate from pinned scores."""

from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

TRACK = "qhe12-explicit-bell-operator-values-v1"
SOURCE_DIGESTS = {
    "normal": "7a42452895eaa8f638e9e73236893e6c869d28892546158d7f4db0113472b5b5",
    "hard": "5700f4524e774918b4c85ca328e5352c05d5e644a5375dfd7652e81823d3bd08",
}
DESCRIPTION = "Get unitary matrix for a phi plus bell circuit and return it."
PINNED_PROMPTS = {
    "normal": "from qiskit import QuantumCircuit\nfrom qiskit.quantum_info import Operator\n"
    "import numpy as np\ndef get_unitary() -> np.ndarray:\n"
    '    """ ' + DESCRIPTION + '\n    """',
    "hard": DESCRIPTION + "\nYou must implement this using a function named `get_unitary` "
    "with no arguments.",
}
PINNED_CHECK = (
    "def check(candidate):\n    result = candidate()\n    solution = QuantumCircuit(2)\n"
    "    solution.h(0)\n    solution.cx(0, 1)\n"
    "    assert Operator(solution).equiv(result), "
    '"Quantum states or operators are not equivalent"\n'
)
REQUIREMENT = (
    "Return a plain NumPy ndarray with shape (4, 4) and finite real or complex numeric "
    "entries representing the complete two-qubit operator for H on qubit 0 followed "
    "by CX with control qubit 0 and target qubit 1. Use computational-basis order "
    "|q1 q0>, with rows indexing output states and columns indexing input states. "
    "All four input basis states are part of this operator contract; preparing "
    "phi-plus from |00> alone is insufficient. Equivalent implementations and an "
    "overall unit-modulus global phase are allowed. Align phase using the nonzero "
    "Frobenius inner product sum(conjugate(expected_entry) * returned_entry), "
    "normalized to unit modulus. After this alignment, matrix "
    "entries are checked with absolute tolerance 1e-10 and zero relative tolerance. "
    "Use signed or unsigned 8/16/32/64-bit integers, 16/32/64-bit real floats, or "
    "64/128-bit complex floats. Either byte order is accepted. Logical array values "
    "are transferred; storage ownership, strides, writeability and dtype metadata "
    "do not affect correctness. Construction methods and native object provenance "
    "are not attested."
)
CHECK = """def check(candidate):
    import numpy as np

    # Independently specified H tensor and basis-index CX; no candidate/SDK
    # simulation is used to produce the expected operator.
    h = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
    cx = np.zeros((4, 4), dtype=complex)
    for column in range(4):
        row = column ^ 2 if column & 1 else column
        cx[row, column] = 1
    wanted = cx @ np.kron(np.eye(2), h)
    actual = candidate()
    assert type(actual) is np.ndarray, 'Expected a plain NumPy ndarray'
    assert actual.shape == (4, 4), 'Incorrect operator shape'
    widths = {'i': (1, 2, 4, 8), 'u': (1, 2, 4, 8), 'f': (2, 4, 8), 'c': (8, 16)}
    assert actual.dtype.itemsize in widths.get(actual.dtype.kind, ()), 'Unsupported numeric dtype'
    assert np.isfinite(actual).all(), 'Nonfinite operator entries'
    # Bound values before phase arithmetic to reject extreme finite inputs.
    assert ((actual.real >= -1 - 1e-10) & (actual.real <= 1 + 1e-10)).all(), 'Invalid real entries'
    assert ((actual.imag >= -1 - 1e-10) & (actual.imag <= 1 + 1e-10)).all(), 'Invalid imag entries'
    # Python complex accumulation avoids NumPy underflow exceptions for tiny
    # invalid entries. Every matrix position has the same role in phase fitting.
    overlap = sum(complex(a) * complex(w).conjugate()
                  for a, w in zip(actual.flat, wanted.flat))
    assert abs(overlap) > 0, 'Missing operator overlap'
    phase = overlap / abs(overlap)
    assert np.allclose(actual, phase * wanted, atol=1e-10, rtol=0), 'Incorrect full operator'
"""


def revised_task(task):
    suite = task.public.suite
    if suite not in SOURCE_DIGESTS:
        raise ValueError("Expected the exact pinned Task 12 source")
    original_check = (
        PINNED_CHECK
        if suite == "normal"
        else "from qiskit import QuantumCircuit\nfrom qiskit.quantum_info import Operator\n"
        + PINNED_CHECK
        + "\ncheck(get_unitary)"
    )
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": PINNED_PROMPTS[suite]}),
            "upstream_test": original_check,
        }
    )
    if source.digest != SOURCE_DIGESTS[suite]:
        raise ValueError("Expected the exact pinned Task 12 source")
    prompt = (
        "from qiskit import QuantumCircuit\nfrom qiskit.quantum_info import Operator\n"
        "import numpy as np\ndef get_unitary() -> np.ndarray:\n" + '    """' + REQUIREMENT + '"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement get_unitary() with no arguments in Python."
    )
    revised = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": CHECK,
        }
    )
    if task.digest not in (source.digest, revised.digest):
        raise ValueError("Expected the exact pinned Task 12 source or its exact revision")
    return revised


class BellOperatorJudge:
    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 3) != 3:
            raise ValueError("Task 12 requires protected value protocol 3")
        for name, default in (
            ("graph_transport", "snapshot-v1"),
            ("graph_batch", "none"),
            ("graph_limits", None),
            ("graph_state_limit", None),
        ):
            if kwargs.pop(name, default) != default:
                raise ValueError("Task 12 requires logical value transport without graph settings")
        kwargs.setdefault("output_limit", 1024 * 1024)
        self.inner = UpstreamJudge(protocol=3, **kwargs)

    def revise(self, task):
        return revised_task(task)

    def configuration(self, task):
        if task.digest != revised_task(task).digest:
            raise ValueError("Revise Task 12 before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": TRACK,
            "source": source_manifest(),
            "source_task_digest": SOURCE_DIGESTS[task.public.suite],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract_digest": task.public.digest,
            "public_contract": REQUIREMENT,
            "calls": 1,
            "expected_operator": "literal H tensor and indexed CX; complete four-column action",
            "runtime_qualification": "unqualified; isolated valid/invalid controls must pass",
            "release_eligible": False,
            "inner": inner,
            "limitations": [
                "This explicit operator task changes the original ambiguous public contract",
                "One no-argument call does not attest other invocations or construction methods",
                "Numeric dtype widths are explicit; extended-precision and object arrays "
                "are outside this condition",
                "Storage relationships and dtype metadata are not transferred or attested",
                "Isolated controls, encoder integrity and independent admission are pending",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

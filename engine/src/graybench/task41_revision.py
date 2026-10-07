"""Exact-source Task41 revision with explicit Pauli subsystem placement."""

from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

TRACK = "qhe41-explicit-pauli-subsystems-values-v1"
SOURCE_DIGESTS = {
    "normal": "2eaae6d3fb7fdef5399ed1d78dd6aee8b0280db0f01750fe203459e5e806109e",
    "hard": "af3f1c7f69f3fb60817415a834e5a4a12c0999f4bd3022b109d0cd3c06d2b50f",
}
PREFIX = "from qiskit.quantum_info.operators import Operator, Pauli\nimport numpy as np\n"
DESCRIPTION = (
    "Compose {pauli} with a 3-qubit identity operator using the Operator and the "
    "Pauli 'YX' class in Qiskit. Return the operator instance."
)
PINNED_PROMPTS = {
    "normal": PREFIX
    + "def compose_op() -> Operator:\n    "
    + '""" '
    + DESCRIPTION.format(pauli="XZ")
    + '\n    """',
    "hard": DESCRIPTION.format(pauli="YX")
    + "\nYou must implement this using a function named `compose_op` with no arguments.",
}
PINNED_CHECK = (
    "def check(candidate):\n    result = candidate()\n    op = Operator(np.eye(2 ** 3))\n"
    "    YX = Operator(Pauli('YX'))\n"
    "    expected = op.compose(YX, qargs=[0, 2], front=True)\n"
    "    assert(result == expected)\n"
)
REQUIREMENT = (
    "Return a plain qiskit.quantum_info.Operator representing the composition of a "
    "three-qubit identity with the two-qubit Pauli 'YX'. Place Pauli local qubit 0 "
    "on global qubit 0 and local qubit 1 on global qubit 2; global qubit 1 is unchanged. "
    "In a Pauli label, the rightmost character is local qubit 0. Use computational "
    "basis order |q2 q1 q0>, rows indexing output and columns indexing input. "
    "Both input_dims() and output_dims() must be (2, 2, 2). The logical matrix must "
    "have shape (8, 8), finite complex64 or complex128 entries, and either byte order. "
    "Compare to the specified Pauli operator at absolute tolerance 1e-10 and zero "
    "relative tolerance; no extra global-phase alignment is performed. "
    "Any construction method producing these logical values and dimensions is "
    "accepted. Operator qargs binding metadata is ignored. Array ownership, strides, "
    "writeability, dtype metadata, constructor use and native object provenance "
    "are not attested by this value condition. Supported matrix values are "
    "reconstructed at complex128 precision without changing their numeric values."
)
CHECK = """def check(candidate):
    import numpy as np
    from qiskit.quantum_info import Operator

    actual = candidate()
    assert type(actual) is Operator, 'Expected a plain Operator'
    assert actual.input_dims() == (2, 2, 2), 'Incorrect input dimensions'
    assert actual.output_dims() == (2, 2, 2), 'Incorrect output dimensions'
    data = actual.data
    assert type(data) is np.ndarray, 'Expected a plain numeric matrix'
    assert data.shape == (8, 8), 'Incorrect operator shape'
    assert data.dtype.kind == 'c' and data.dtype.itemsize in (8, 16), 'Unsupported dtype'
    assert np.isfinite(data).all(), 'Nonfinite operator entries'
    assert ((data.real >= -1 - 1e-10) & (data.real <= 1 + 1e-10)).all(), 'Invalid real entries'
    assert ((data.imag >= -1 - 1e-10) & (data.imag <= 1 + 1e-10)).all(), 'Invalid imag entries'
    # Independently derive every basis action: X flips q0, Y flips q2 with
    # amplitude i for input q2=0 and -i for input q2=1. q1 is unchanged.
    wanted = np.zeros((8, 8), dtype=complex)
    for column in range(8):
        wanted[column ^ 5, column] = -1j if column & 4 else 1j
    assert np.allclose(data, wanted, atol=1e-10, rtol=0), 'Incorrect full operator'
"""


def revised_task(task):
    suite = task.public.suite
    if suite not in SOURCE_DIGESTS:
        raise ValueError("Expected the exact pinned Task 41 source")
    original_check = (
        PINNED_CHECK if suite == "normal" else PREFIX + PINNED_CHECK + "\ncheck(compose_op)"
    )
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": PINNED_PROMPTS[suite]}),
            "upstream_test": original_check,
        }
    )
    if source.digest != SOURCE_DIGESTS[suite]:
        raise ValueError("Expected the exact pinned Task 41 source")
    prompt = (
        PREFIX + "def compose_op() -> Operator:\n    " + '"""' + REQUIREMENT + '"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement compose_op() with no arguments in Python."
    )
    revision = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": CHECK,
        }
    )
    if task.digest not in (source.digest, revision.digest):
        raise ValueError("Expected the exact pinned Task 41 source or its exact revision")
    return revision


class PauliSubsystemJudge:
    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 3) != 3:
            raise ValueError("Task 41 requires protected value protocol 3")
        for name, default in (
            ("graph_transport", "snapshot-v1"),
            ("graph_batch", "none"),
            ("graph_limits", None),
            ("graph_state_limit", None),
        ):
            if kwargs.pop(name, default) != default:
                raise ValueError("Task 41 requires logical value transport without graph settings")
        kwargs.setdefault("output_limit", 1024 * 1024)
        self.inner = UpstreamJudge(protocol=3, **kwargs)

    def revise(self, task):
        return revised_task(task)

    def configuration(self, task):
        if task.digest != revised_task(task).digest:
            raise ValueError("Revise Task 41 before generation and judgment")
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
            "expected_operator": "Independent eight-column basis action; fixed Pauli phase",
            "operator_binding_metadata": "qargs ignored; matrix and subsystem dimensions only",
            "numeric_projection": "Supported entry values reconstructed as complex128",
            "runtime_qualification": "unqualified; isolated valid/invalid controls must pass",
            "release_eligible": False,
            "inner": inner,
            "limitations": [
                "The revision resolves contradictory labels and discloses subsystem placement",
                "Constructor/Pauli use and binding metadata are not attested",
                "One no-argument call does not attest other invocations",
                "Isolated controls, candidate encoder integrity and independent admission "
                "are pending",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

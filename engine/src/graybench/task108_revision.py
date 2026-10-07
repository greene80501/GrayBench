"""Development-only all-value Choi condition; exact pinned ancestry is retained."""

from graybench.datasets import JudgeTask
from graybench.graph_limits import GraphLimits
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

TRACK = "qhe108-choi-values-graph-v1"
SOURCE_DIGESTS = {
    "normal": "37f0d8dab549f91ee6960add0bfba01135fd36cd05f60f31fc62d738e47c5f9d",
    "hard": "4c80e1d2943add5b96a5ef85f32dda48d4ebddd9738b58d4bb4e2e64e5168e07",
}
REQUIREMENT = (
    "Given same-sized finite complex NumPy arrays data1 and data2 of shape "
    "(4**n, 4**n), for a positive integer n, interpreted as Choi matrices of "
    "square linear maps on n qubits, return exactly three Qiskit Choi values "
    "in order: the map represented by data1, its channel adjoint, and the "
    "composition applying data1 first and data2 second (Qiskit's default "
    "Choi(data1).compose(Choi(data2)) convention). The channel adjoint is "
    "the Hermitian adjoint in SuperOp representation, not generally the "
    "Hermitian transpose of the Choi matrix. Complete positivity and trace "
    "preservation are not assumed. All returned matrices must have the same "
    "input/output dimensions as the supplied maps and finite entries. Data "
    "are checked with absolute tolerance 1e-8 and relative tolerance 1e-10; "
    "an overall phase or scale on a Choi matrix is not ignored. Inputs may "
    "be modified, but results must describe their original values. Equivalent "
    "constructions and return-value aliasing are allowed; construction methods "
    "and native object provenance are not attested."
)
CHECK = """def check(candidate):
    import numpy as np
    from qiskit.quantum_info import Choi

    def unitary_choi(operator):
        vector = operator.reshape(-1, order='F')
        return np.outer(vector, vector.conj())

    def expectations(first, second, d):
        # J[i*d+a,j*d+b] = E(|i><j|)[a,b]. Work directly with those blocks.
        adjoint = np.empty_like(first, dtype=complex)
        composed = np.zeros_like(first, dtype=complex)
        for i in range(d):
            for j in range(d):
                for a in range(d):
                    for b in range(d):
                        adjoint[i*d+a,j*d+b] = first[a*d+i,b*d+j].conjugate()
                        composed[i*d:(i+1)*d,j*d:(j+1)*d] += (
                            first[i*d+a,j*d+b] * second[a*d:(a+1)*d,b*d:(b+1)*d]
                        )
        return first.copy(), adjoint, composed

    pairs = [(np.eye(4, dtype=complex), np.eye(4, dtype=complex), 2)]
    for n in (1, 2, 3):
        d = 2**n
        h = np.array([[1,1],[1,-1]], dtype=complex) / np.sqrt(2)
        s = np.diag([1,1j])
        u, v = h, s
        for _ in range(n-1):
            u, v = np.kron(u, h), np.kron(v, s)
        uj, vj = unitary_choi(u), unitary_choi(v)
        k0 = np.kron(np.diag([1,np.sqrt(0.63)]), np.eye(d//2))
        k1 = np.kron(np.array([[0,np.sqrt(0.37)],[0,0]]), np.eye(d//2))
        damping = unitary_choi(k0) + unitary_choi(k1)
        rows, cols = np.indices((d*d,d*d))
        first = ((3*rows+cols)%11-5 + 1j*((rows+5*cols)%13-6)) / 16
        second = ((rows+2*cols)%7-3 + 1j*((4*rows+cols)%9-4)) / 13
        pairs.extend((a,b,d) for a,b in (
            (uj,vj), (vj,uj), (damping,uj), (uj,damping),
            (first,second), (first,np.zeros_like(second)),
        ))
    for first, second, d in pairs:
        wanted = expectations(first.copy(), second.copy(), d)
        actual = tuple(candidate(first.copy(), second.copy()))
        assert len(actual) == 3, 'Expected exactly three Choi values'
        for index, (value, expected) in enumerate(zip(actual, wanted)):
            assert isinstance(value, Choi), 'Expected a Choi value'
            assert value.dim == (d,d), 'Incorrect channel dimensions'
            data = np.asarray(value.data)
            assert data.shape == expected.shape, 'Incorrect Choi shape'
            assert np.isfinite(data).all(), 'Nonfinite Choi data'
            assert np.allclose(data, expected, atol=1e-8, rtol=1e-10), (
                'Incorrect Choi value at return position ' + str(index)
            )
"""
PINNED_DESCRIPTION = (
    "Initialize Choi matrices for the given data1 and data2 as inputs. Compute data1 "
    "adjoint, and then return the data1 Choi matrix, its adjoint and the composed "
    "choi matrices in order."
)
PINNED_PROMPTS = {
    "normal": (
        "from qiskit.quantum_info import Choi\nimport numpy as np\n"
        "def initialize_adjoint_and_compose(data1: np.ndarray, data2: np.ndarray) "
        '-> (Choi, Choi, Choi):\n    """ ' + PINNED_DESCRIPTION + '\n    """'
    ),
    "hard": PINNED_DESCRIPTION + "\nYou must implement this using a function named "
    "`initialize_adjoint_and_compose` with the following arguments: data1, data2.",
}
PINNED_CHECK = """def check(candidate):
    data = np.eye(4)
    choi, adjoint_choi, composed_choi = candidate(data, data)
    assert isinstance(choi, Choi), f'Expected Choi, got {type(choi).__name__}'
    assert choi.dim == (2, 2), f'Expected dimensions (2, 2), got {choi.dim}'
    assert isinstance(adjoint_choi, Choi), f'Expected Choi, got {type(adjoint_choi).__name__}'
    assert isinstance(composed_choi, Choi), f'Expected Choi, got {type(composed_choi).__name__}'
    expected_adjoint_data = data.conj().T
""" + (
    "    assert np.allclose(adjoint_choi.data, expected_adjoint_data), "
    "f'Expected adjoint data to be {expected_adjoint_data}, but got {adjoint_choi.data}'"
)


def revised_task(task: JudgeTask) -> JudgeTask:
    suite = task.public.suite
    if suite not in SOURCE_DIGESTS:
        raise ValueError("Expected the exact pinned QHE task-108 source")
    source = task.model_copy(
        update={
            "public": task.public.model_copy(update={"prompt": PINNED_PROMPTS[suite]}),
            "upstream_test": PINNED_CHECK
            if suite == "normal"
            else "from qiskit.quantum_info import Choi\nimport numpy as np\n"
            + PINNED_CHECK
            + "\ncheck(initialize_adjoint_and_compose)",
        }
    )
    if source.digest != SOURCE_DIGESTS[suite]:
        raise ValueError("Expected the exact pinned QHE task-108 source")
    prompt = (
        "from qiskit.quantum_info import Choi\nimport numpy as np\n"
        "def initialize_adjoint_and_compose(data1: np.ndarray, data2: np.ndarray):\n"
        + '    """'
        + REQUIREMENT
        + '"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement initialize_adjoint_and_compose(data1, data2) in Python."
    )
    revised = source.model_copy(
        update={
            "public": source.public.model_copy(update={"prompt": prompt}),
            "upstream_test": CHECK,
        }
    )
    if task.digest not in (source.digest, revised.digest):
        raise ValueError("Expected the exact pinned QHE task-108 source or its exact revision")
    return revised


class ChoiValuesJudge:
    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 4) != 4:
            raise ValueError("Task 108 revision requires graph protocol 4")
        if kwargs.pop("graph_transport", "delta-v1") != "delta-v1":
            raise ValueError("Task 108 revision requires delta graph transport")
        if kwargs.pop("graph_batch", "none") != "none":
            raise ValueError("Task 108 revision requires individual calls")
        kwargs.setdefault("output_limit", 16 * 1024 * 1024)
        limits = GraphLimits(
            message_bytes=kwargs["output_limit"],
            array_bytes=4 * 1024 * 1024,
            matrix_bytes=4 * 1024 * 1024,
        )
        if kwargs.pop("graph_limits", limits) != limits:
            raise ValueError("Task 108 revision requires its frozen graph resource bounds")
        self.inner = UpstreamJudge(
            protocol=4, graph_transport="delta-v1", graph_limits=limits, **kwargs
        )

    def revise(self, task):
        return revised_task(task)

    def configuration(self, task):
        if task.digest != revised_task(task).digest:
            raise ValueError("Revise task 108 before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": TRACK,
            "release_eligible": False,
            "source": source_manifest(),
            "pinned_source_task_digest": SOURCE_DIGESTS[task.public.suite],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract": REQUIREMENT,
            "input_mutation": "permitted; expectations frozen before dispatch",
            "inner": inner,
            "limitations": [
                "19 authored input pairs do not exhaust the public matrix domain",
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
            {"manifest": manifest, "inner": result.evidence},
        )

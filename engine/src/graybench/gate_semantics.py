"""Explicit behavioral revisions for gate tasks, separate from upstream replication."""

from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

EVOLUTION_CONTRACT = (
    "For this behavioral track, return a QuantumCircuit on exactly len(pauli_string) qubits "
    "representing exp(-i*time*P), where P is the supplied nonempty I/X/Y/Z Pauli string "
    "in Qiskit's qubit order and time is real. Matrix entries, including global phase, "
    "are compared with absolute tolerance 1e-10 and zero relative tolerance. "
    "This track scores the returned circuit semantics; the choice of synthesis routine "
    "is not scored, and equivalent implementations are allowed."
)
DIAGONAL_CONTRACT = (
    "For this behavioral track, valid diag inputs have power-of-two length at least two "
    "and unit-modulus complex entries. Return a QuantumCircuit with the corresponding "
    "qubit count whose operator is the given diagonal in Qiskit's computational-basis "
    "order. An overall unit-modulus global phase is allowed. Matrix entries after phase "
    "alignment use absolute tolerance 1e-10 and zero relative tolerance. Do not mutate "
    "diag. This track scores returned circuit semantics; the choice of construction "
    "routine is not scored, and equivalent implementations are allowed."
)

EVOLUTION_CHECK = """def check(candidate):
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Operator
    from qiskit.exceptions import QiskitError
    basis = {
        'I': np.eye(2, dtype=complex),
        'X': np.array([[0, 1], [1, 0]], dtype=complex),
        'Y': np.array([[0, -1j], [1j, 0]], dtype=complex),
        'Z': np.array([[1, 0], [0, -1]], dtype=complex),
    }
    cases = (('I', 0.0), ('I', 0.37), ('X', 1.0), ('X', -0.23),
             ('Y', 0.41), ('Z', -0.61), ('XI', 0.29), ('IX', 0.29),
             ('YZ', -0.47), ('ZY', -0.47), ('ZZ', 0.0), ('II', 0.73),
             ('XYZ', 0.19), ('ZYX', -0.53), ('IXYZ', 0.11), ('ZYXI', -0.31))
    for label, time in cases:
        circuit = candidate(label, time)
        assert isinstance(circuit, QuantumCircuit), 'Expected QuantumCircuit'
        assert circuit.num_qubits == len(label), 'Wrong circuit width'
        pauli = np.ones((1, 1), dtype=complex)
        for char in label:
            pauli = np.kron(pauli, basis[char])
        # P squared is identity for every tested unsigned Pauli tensor product.
        expected = np.cos(time) * np.eye(2**len(label)) - 1j * np.sin(time) * pauli
        try:
            actual = Operator(circuit).data
        except (QiskitError, ValueError, TypeError) as exc:
            raise AssertionError('Circuit does not define an operator') from exc
        assert np.isfinite(actual).all(), 'Non-finite operator'
        assert np.allclose(actual, expected, atol=1e-10, rtol=0), 'Incorrect Pauli evolution'
"""

DIAGONAL_CHECK = """def check(candidate):
    import numpy as np
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Operator
    from qiskit.exceptions import QiskitError
    cases = [[1, 1j, -1, -1j], [1, 1], [1, -1], [1j, -1j]]
    for width in range(1, 5):
        for shift in (0.0, 0.37):
            cases.append([complex(np.exp(1j * (0.19 * k*k - 0.41*k + shift)))
                          for k in range(2**width)])
    for given in cases:
        # Independent expected values, not a DiagonalGate reconstruction.
        expected = np.diag(given)
        circuit = candidate(list(given))
        assert isinstance(circuit, QuantumCircuit), 'Expected QuantumCircuit'
        assert 2**circuit.num_qubits == len(given), 'Wrong circuit width'
        try:
            actual = Operator(circuit).data
        except (QiskitError, ValueError, TypeError) as exc:
            raise AssertionError('Circuit does not define an operator') from exc
        assert np.isfinite(actual).all(), 'Non-finite operator'
        phase = actual[0, 0] / given[0]
        assert abs(phase) > 0, 'Missing diagonal entry'
        phase /= abs(phase)
        assert np.allclose(actual, phase * expected, atol=1e-10, rtol=0), 'Incorrect diagonal'
"""

REVISIONS = {
    "qhe116-evolution-semantics-v1": (
        "qhe/116",
        "synthesize_evolution_gate",
        EVOLUTION_CONTRACT,
        EVOLUTION_CHECK,
        "Sixteen fixed Pauli/time pairs on one to four qubits; finite coverage only",
    ),
    "qhe120-diagonal-semantics-v1": (
        "qhe/120",
        "create_diagonal_circuit",
        DIAGONAL_CONTRACT,
        DIAGONAL_CHECK,
        "Twelve fixed diagonals on one to four qubits; finite coverage only",
    ),
}


class GateSemanticsJudge:
    def __init__(self, recipe, **kwargs):
        if recipe not in REVISIONS:
            raise ValueError("Unknown gate semantics revision")
        self.recipe = recipe
        self.inner = UpstreamJudge(**kwargs)

    def revise(self, task):
        family, entry, contract, check, _ = REVISIONS[self.recipe]
        if task.public.family_id != family or task.public.entry_point != entry:
            raise ValueError("Gate semantics revision requires matching family and entry point")
        addition = "\n    # " if task.public.prompt_format == "function_completion" else "\n"
        addition += contract + "\n"
        prompt = task.public.prompt
        if not prompt.endswith(addition):
            prompt += addition
        return task.model_copy(
            update={
                "public": task.public.model_copy(update={"prompt": prompt}),
                "upstream_test": check,
            }
        )

    def configuration(self, task):
        revised = self.revise(task)
        if task.digest != revised.digest:
            raise ValueError("Revise the task before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": self.recipe,
            "source": source_manifest(),
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract": REVISIONS[self.recipe][2],
            "domain": REVISIONS[self.recipe][4],
            "inner": inner,
            "release_eligible": False,
            "limitations": [
                "Internal synthesis/construction procedure is not scored",
                "Finite authored cases are not exhaustive or independent certification",
                "Input mutation and unsupported representations remain unscored",
                "Operator extraction still depends on the pinned Qiskit runtime",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

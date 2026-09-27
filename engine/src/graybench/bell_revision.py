"""Explicit task-2 Bell-state development recipe, separate from pinned scoring."""

from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

BELL_CONTRACT = (
    "Return a Qiskit Statevector with exactly two qubits representing Phi+ up to global phase. "
    "Amplitudes are compared with absolute tolerance 1e-10 and zero relative tolerance."
)

BELL_CHECK = """def check(candidate):
    import numpy as np
    from qiskit.quantum_info import Statevector
    from qiskit.quantum_info.operators.op_shape import OpShape
    result = candidate()
    assert isinstance(result, Statevector), 'Expected a Qiskit Statevector'
    state = object.__getattribute__(result, '__dict__')
    assert type(state) is dict, 'Invalid Statevector state'
    shape = state.get('_op_shape')
    assert type(shape) is OpShape, 'Invalid Statevector shape'
    dimensions = object.__getattribute__(shape, '__dict__')
    left_dims = dimensions.get('_dims_l')
    assert (type(dimensions.get('_num_qargs_l')) is int
            and dimensions['_num_qargs_l'] == 2
            and type(dimensions.get('_num_qargs_r')) is int
            and dimensions['_num_qargs_r'] == 0
            and (left_dims is None or (type(left_dims) is tuple and left_dims == (2, 2)))
            and dimensions.get('_dims_r') is None), 'Expected two qubits'
    raw_data = state.get('_data')
    assert type(raw_data) is np.ndarray, 'Expected numeric Statevector data'
    assert raw_data.dtype.kind in 'biufc', 'Expected numeric Statevector data'
    actual = np.array(raw_data, dtype=complex, copy=True)
    assert actual.shape == (4,), 'Wrong statevector shape'
    assert np.isfinite(actual).all(), 'Non-finite state amplitude'
    expected = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    overlap = np.vdot(expected, actual)
    assert abs(overlap) > 0, 'Orthogonal to Phi+'
    phase = overlap / abs(overlap)
    assert np.allclose(actual, phase * expected, atol=1e-10, rtol=0), 'Incorrect Phi+ state'
"""


class BellStatevectorJudge:
    """Strengthen observable return semantics without changing the upstream track."""

    def __init__(self, **kwargs):
        self.inner = UpstreamJudge(**kwargs)

    def revise(self, task):
        if (
            task.public.family_id != "qhe/2"
            or task.public.task_id != "qiskitHumanEval/2"
            or task.public.entry_point != "create_bell_statevector"
        ):
            raise ValueError("Bell-state revision requires task 2")
        addition = (
            ("\n    # " if task.public.prompt_format == "function_completion" else "\n")
            + BELL_CONTRACT
            + "\n"
        )
        prompt = task.public.prompt
        if not prompt.endswith(addition):
            prompt += addition
        return task.model_copy(
            update={
                "public": task.public.model_copy(update={"prompt": prompt}),
                "upstream_test": BELL_CHECK,
            }
        )

    def configuration(self, task):
        revised = self.revise(task)
        if task.digest != revised.digest:
            raise ValueError("Revise the task before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": "qhe2-bell-statevector-v1",
            "source": source_manifest(),
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract": BELL_CONTRACT,
            "domain": "One no-argument two-qubit Phi+ Statevector, up to global phase",
            "inner": inner,
            "release_eligible": False,
            "limitations": [
                "Protected normal/hard execution and independent domain review remain pending",
                "This checks returned amplitudes, not the construction procedure",
                "Candidate and encoder share a process; arbitrary encoder patching is unresolved",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

"""Development-only Bell-amplitude value revision descended from QHE task 2.

The pinned task asks for a Statevector. This revision asks only for its four
complex amplitudes, so it cannot attest native object identity or construction.
"""

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.protected_semantic_judge import (
    TASK2_ORACLE,
    ProtectedSemanticTask,
    SemanticCase,
)
from graybench.protected_value_contract import ProtectedValueContract, ValueCall, ValueShape

TASK2_SOURCE_DIGESTS = {
    "normal": "a78bfe9a998849b69a9fb0b4e781a2a1d3299e2b89948eae7842d9594f4a429f",
    "hard": "3eade3264d5638c1bd66d1a9630d9388137498b2b98e202066c3ddeb49784d88",
}

REQUIREMENT = (
    "Return a length-4 list of [real, imaginary] amplitude pairs in Qiskit's "
    "little-endian two-qubit statevector order for Phi+ = (|00> + |11>) / sqrt(2). "
    "Each component must be finite and in [-1,1]. An arbitrary global phase is "
    "allowed. After global-phase alignment, norm and every amplitude are checked "
    "with absolute tolerance 1e-10 and zero relative tolerance. Return the "
    "value directly. Qiskit is allowed, but only the returned value is checked; "
    "Statevector identity or circuit construction is not attested."
)


def task2_value_task(source: JudgeTask) -> ProtectedSemanticTask:
    suite = source.public.suite
    if source.public.task_id != "qiskitHumanEval/2" or source.digest != TASK2_SOURCE_DIGESTS[suite]:
        raise ValueError("Expected the exact pinned QHE task-2 source")
    if suite == "normal":
        prompt_format = "function_completion"
        prompt = f'def bell_amplitudes():\n    """{REQUIREMENT}"""\n'
    else:
        prompt_format = "standalone_function"
        prompt = REQUIREMENT + " Implement `bell_amplitudes()` in Python."
    scalar = ValueShape(kind="number", minimum=-1.0, maximum=1.0)
    pair = ValueShape(kind="array", item=scalar, min_items=2, max_items=2)
    contract = ProtectedValueContract(
        source_task_digest=source.digest,
        public=PublicTask(
            suite=suite,
            task_id=source.public.task_id,
            family_id=source.public.family_id,
            prompt=prompt,
            entry_point="bell_amplitudes",
            prompt_format=prompt_format,
        ),
        positional=(),
        result=ValueShape(kind="array", item=pair, min_items=4, max_items=4),
    )
    return ProtectedSemanticTask(
        contract=contract,
        oracle=TASK2_ORACLE,
        cases=(SemanticCase(case_id="bell-phi-plus", call=ValueCall()),),
    )

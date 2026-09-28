"""Development-only value revision descended from pinned QHE task 20.

The original task asks for a transpiled QuantumCircuit using a pass manager.
This revision asks only for amplitudes and cannot verify how they were made.
"""

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.protected_semantic_judge import ProtectedSemanticTask, SemanticCase
from graybench.protected_value_contract import (
    ProtectedValueContract,
    ValueCall,
    ValueShape,
)

TASK20_SOURCE_DIGESTS = {
    "normal": "50c85aa2a066db0be117730d7b916d7522ccb282002b802ee1a9112c405571ad",
    "hard": "a39d624d99ec39b312f116204d9c9d4af41ca3f89ab07005bbea2952d456c217",
}

REQUIREMENT = (
    "For a list of three distinct physical wire indices from 0 through 6, "
    "return a length-128 list of [real, imaginary] amplitude pairs in Qiskit's "
    "little-endian statevector order. The normalized state must be GHZ+ on "
    "those three wires, with the other four wires at zero; global phase is "
    "irrelevant. Return the value directly. Using Qiskit is allowed but the "
    "result is checked only as a value, not as a QuantumCircuit or evidence "
    "of a pass-manager call."
)


def task20_value_task(source: JudgeTask) -> ProtectedSemanticTask:
    suite = source.public.suite
    if (
        source.public.task_id != "qiskitHumanEval/20"
        or source.digest != TASK20_SOURCE_DIGESTS[suite]
    ):
        raise ValueError("Expected the exact pinned QHE task-20 source")
    if suite == "normal":
        prompt_format = "function_completion"
        prompt = f'def ghz_amplitudes(layout):\n    """{REQUIREMENT}"""\n'
    else:
        prompt_format = "standalone_function"
        prompt = REQUIREMENT + " Implement `ghz_amplitudes(layout)` in Python."
    # Every real or imaginary component of a normalized state is in [-1, 1].
    # This bound also prevents nonphysical finite values from overflowing the oracle.
    scalar = ValueShape(kind="number", minimum=-1.0, maximum=1.0)
    amplitude = ValueShape(kind="array", item=scalar, min_items=2, max_items=2)
    contract = ProtectedValueContract(
        source_task_digest=source.digest,
        public=PublicTask(
            suite=suite,
            task_id=source.public.task_id,
            family_id=source.public.family_id,
            prompt=prompt,
            entry_point="ghz_amplitudes",
            prompt_format=prompt_format,
        ),
        positional=(
            ValueShape(
                kind="array",
                item=ValueShape(kind="integer", minimum=0, maximum=6),
                min_items=3,
                max_items=3,
            ),
        ),
        result=ValueShape(kind="array", item=amplitude, min_items=128, max_items=128),
    )
    return ProtectedSemanticTask(
        contract=contract,
        cases=(
            SemanticCase(case_id="source-layout", call=ValueCall(args=([2, 4, 6],))),
            SemanticCase(case_id="adjacent-layout", call=ValueCall(args=([0, 1, 2],))),
            SemanticCase(case_id="sparse-layout", call=ValueCall(args=([1, 3, 5],))),
        ),
    )

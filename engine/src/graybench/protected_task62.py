"""Development-only BB84 sender amplitude revision of pinned QHE task 62.

The original asks for a QuantumCircuit. This revision checks only the returned
statevector value and therefore makes no native-object or gate-use claim.
"""

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.protected_semantic_judge import (
    TASK62_ORACLE,
    TASK62_ORACLE_V2,
    ProtectedSemanticTask,
    SemanticCase,
    task62_case_pairs,
    task62_case_pairs_v2,
)
from graybench.protected_value_contract import ProtectedValueContract, ValueCall, ValueShape

TASK62_SOURCE_DIGESTS = {
    "normal": "1754a3024c36ffbd226cde5dfded2cfdd97bc2f121c5836c26193dc044b653b2",
    "hard": "3fdac895c092fbf2c530b53e1d3a5be17d5892e658a95986d3d3f744135f1e06",
}

REQUIREMENT = (
    "Given equal-length lists state and basis of binary integers, with length 1 "
    "through 5, return the ideal BB84 sender state as a list of [real, imaginary] "
    "amplitude pairs in Qiskit's little-endian statevector order. For qubit i, "
    "basis[i]=0 uses Z and basis[i]=1 uses X; state[i]=0 or 1 selects |0> "
    "or |1> in Z and |+> or |-> in X. Each component must be finite and in "
    "[-1,1]. Global phase is allowed. Norm and phase-aligned amplitudes are "
    "checked with absolute tolerance 1e-10 and zero relative tolerance. "
    "Return the value directly; Qiskit is allowed, but circuit identity and "
    "construction are not attested."
)


def task62_value_task(source: JudgeTask) -> ProtectedSemanticTask:
    suite = source.public.suite
    if (
        source.public.task_id != "qiskitHumanEval/62"
        or source.digest != TASK62_SOURCE_DIGESTS[suite]
    ):
        raise ValueError("Expected the exact pinned QHE task-62 source")
    if suite == "normal":
        prompt_format = "function_completion"
        prompt = f'def bb84_sender_amplitudes(state, basis):\n    """{REQUIREMENT}"""\n'
    else:
        prompt_format = "standalone_function"
        prompt = REQUIREMENT + " Implement `bb84_sender_amplitudes(state, basis)` in Python."
    bit = ValueShape(kind="integer", minimum=0, maximum=1)
    bits = ValueShape(kind="array", item=bit, min_items=1, max_items=5)
    scalar = ValueShape(kind="number", minimum=-1.0, maximum=1.0)
    pair = ValueShape(kind="array", item=scalar, min_items=2, max_items=2)
    contract = ProtectedValueContract(
        source_task_digest=source.digest,
        public=PublicTask(
            suite=suite,
            task_id=source.public.task_id,
            family_id=source.public.family_id,
            prompt=prompt,
            entry_point="bb84_sender_amplitudes",
            prompt_format=prompt_format,
        ),
        positional=(bits, bits),
        result=ValueShape(kind="array", item=pair, min_items=2, max_items=32),
    )
    return ProtectedSemanticTask(
        contract=contract,
        oracle=TASK62_ORACLE,
        cases=tuple(
            SemanticCase(
                case_id=(
                    f"width-{len(state)}-state-{''.join(map(str, state))}"
                    f"-basis-{''.join(map(str, basis))}"
                ),
                call=ValueCall(args=(list(state), list(basis))),
            )
            for state, basis in task62_case_pairs()
        ),
    )


def task62_value_task_v2(source: JudgeTask) -> ProtectedSemanticTask:
    """Judge every valid input while keeping the original value contract."""
    original = task62_value_task(source)
    return ProtectedSemanticTask(
        contract=original.contract,
        oracle=TASK62_ORACLE_V2,
        cases=tuple(
            SemanticCase(
                case_id=(
                    f"width-{len(state)}-state-{''.join(map(str, state))}"
                    f"-basis-{''.join(map(str, basis))}"
                ),
                call=ValueCall(args=(list(state), list(basis))),
            )
            for state, basis in task62_case_pairs_v2()
        ),
    )

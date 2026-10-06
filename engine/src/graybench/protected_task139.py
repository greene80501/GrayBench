"""Development-only four-qubit Schmidt value revision of pinned QHE task 139."""

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.protected_semantic_judge import (
    TASK139_ORACLE,
    ProtectedSemanticTask,
    SemanticCase,
    task139_case_inputs,
)
from graybench.protected_value_contract import ProtectedValueContract, ValueCall, ValueShape

TASK139_SOURCE_DIGESTS = {
    "normal": "a50601a7a1d7082bf18e6ed1f7da0668d576337110eb05efccf5532909c5b843",
    "hard": "15d406b88ab2513fd0e084cb28ec284399e1fd58668e4ed3b497267693956cd6",
}

REQUIREMENT = (
    "Given a normalized four-qubit pure state as 16 [real, imaginary] amplitude pairs "
    "in Qiskit little-endian statevector order and a nonempty proper list qargs_B "
    "of distinct qubit indices 0..3, return its Schmidt terms. Return a nonempty "
    "list of at most min(2**len(qargs_B), 2**(4-len(qargs_B))) objects, each with "
    "exactly the keys weight, a, b. weight is a strictly positive real Schmidt "
    "coefficient; a and b are normalized, mutually orthogonal subsystem vectors "
    "as [real, imaginary] pairs. The A subsystem is the ascending complement "
    "of qargs_B; the B subsystem uses sorted qargs_B, even when the input list "
    "is unsorted. Both use little-endian indexing within the subsystem. The "
    "weighted tensor products must reconstruct the state up to global phase; "
    "norms, orthogonality, squared-weight sum, and maximum phase-aligned "
    "amplitude error are checked with absolute tolerance 1e-8 and zero relative "
    "tolerance. Term order, phases, and valid rotations of degenerate Schmidt "
    "subspaces are allowed. Return the value directly; native Statevector "
    "identity and algorithm use are not attested."
)


def task139_value_task(source: JudgeTask) -> ProtectedSemanticTask:
    suite = source.public.suite
    if (
        source.public.task_id != "qiskitHumanEval/139"
        or source.digest != TASK139_SOURCE_DIGESTS.get(suite)
    ):
        raise ValueError("Expected the exact pinned QHE task-139 source")
    if suite == "normal":
        prompt_format = "function_completion"
        prompt = f'def schmidt_terms(state, qargs_B):\n    """{REQUIREMENT}"""\n'
    else:
        prompt_format = "standalone_function"
        prompt = REQUIREMENT + " Implement `schmidt_terms(state, qargs_B)` in Python."
    number = ValueShape(kind="number", minimum=-1.0, maximum=1.0)
    pair = ValueShape(kind="array", item=number, min_items=2, max_items=2)
    amplitudes = ValueShape(kind="array", item=pair, min_items=2, max_items=8)
    term = ValueShape(
        kind="object",
        properties={
            "weight": ValueShape(kind="number", minimum=0.0, maximum=1.0),
            "a": amplitudes,
            "b": amplitudes,
        },
        required=("weight", "a", "b"),
        min_items=3,
        max_items=3,
    )
    contract = ProtectedValueContract(
        source_task_digest=source.digest,
        public=PublicTask(
            suite=suite,
            task_id=source.public.task_id,
            family_id=source.public.family_id,
            prompt=prompt,
            entry_point="schmidt_terms",
            prompt_format=prompt_format,
        ),
        positional=(
            ValueShape(kind="array", item=pair, min_items=16, max_items=16),
            ValueShape(
                kind="array",
                item=ValueShape(kind="integer", minimum=0, maximum=3),
                min_items=1,
                max_items=3,
            ),
        ),
        result=ValueShape(kind="array", item=term, min_items=1, max_items=4),
    )
    return ProtectedSemanticTask(
        contract=contract,
        oracle=TASK139_ORACLE,
        cases=tuple(
            SemanticCase(
                case_id=f"partition-{''.join(map(str, partition))}-state-{index}",
                call=ValueCall(args=(state, partition)),
            )
            for index, (state, partition) in enumerate(task139_case_inputs())
        ),
    )

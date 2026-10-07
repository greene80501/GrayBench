"""Explicit matrix-value revision; neither native circuit identity nor synthesis is scored."""

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.evolution_value import TASK116_ORACLE, evolution_case_inputs
from graybench.matrix_task_sources import SOURCE_RECORDS
from graybench.protected_semantic_judge import ProtectedSemanticTask, SemanticCase
from graybench.protected_value_contract import ProtectedValueContract, ValueCall, ValueShape

REQUIREMENT = (
    "Given a nonempty string pauli_string of 1 to 5 I/X/Y/Z letters and a finite real "
    "time, return the complex matrix of exp(-i*time*P), where P is that unsigned "
    "Pauli tensor in Qiskit computational-basis order: the rightmost letter acts "
    "on qubit 0. Return a Python list of 2**len(pauli_string) rows, each a list "
    "of that many entries. Every entry is exactly [real, imaginary] using finite "
    "Python int/float values, with rows and columns in ascending basis-index order. "
    "The maximum absolute complex-entry error must be at most 1e-10; relative "
    "tolerance is zero. Global phase is retained, including for all-I inputs. "
    "Equivalent algorithms and Qiskit-derived or direct mathematical values are "
    "allowed. Return the matrix value directly, rather than an ndarray or circuit. "
    "Circuit identity, native storage, and use of a synthesis routine are not attested."
)


def task116_value_task(source: JudgeTask) -> ProtectedSemanticTask:
    suite = source.public.suite
    if source.public.task_id != "qiskitHumanEval/116" or source.digest != SOURCE_RECORDS.get(
        (116, suite), {}
    ).get("digest"):
        raise ValueError("Expected the exact pinned QHE task-116 source")
    prompt = (
        f'def evolution_matrix(pauli_string, time):\n    """{REQUIREMENT}"""\n'
        if suite == "normal"
        else REQUIREMENT + " Implement `evolution_matrix(pauli_string, time)` in Python."
    )
    pair = ValueShape(kind="array", item=ValueShape(kind="number"), min_items=2, max_items=2)
    row = ValueShape(kind="array", item=pair, min_items=2, max_items=32)
    contract = ProtectedValueContract(
        source_task_digest=source.digest,
        public=PublicTask(
            suite=suite,
            task_id=source.public.task_id,
            family_id=source.public.family_id,
            prompt=prompt,
            entry_point="evolution_matrix",
            prompt_format=source.public.prompt_format,
        ),
        positional=(ValueShape(kind="string", max_length=5), ValueShape(kind="number")),
        result=ValueShape(kind="array", item=row, min_items=2, max_items=32),
    )
    return ProtectedSemanticTask(
        contract=contract,
        oracle=TASK116_ORACLE,
        cases=tuple(
            SemanticCase(
                case_id=f"evolution-{index}-{label}",
                call=ValueCall(args=(label, time)),
            )
            for index, (label, time) in enumerate(evolution_case_inputs())
        ),
    )

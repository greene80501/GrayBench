"""Development-only most-common BitArray condition with order-diverse cases."""

from graybench.identity import identity
from graybench.judge import Judgment
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

RECIPE = "qhe149-most-common-bitstring-v1"
ENTRY = "most_common_result"
PINNED_SOURCE_TASK_DIGESTS = {
    "normal": "363fe9e4032fcc9e3f16d0b38d41a9a7233dcee7c31728efc1f566cafc2bd013",
    "hard": "8071f037bf801abf0d2f16851d538e5656baadd6cda5a19fa69cd6eba17096bf",
}
PUBLIC_CONTRACT = (
    "For a nonempty BitArray containing equal-width binary strings with a unique most "
    "frequent string, return that string as Python str. Counts and insertion order may vary. "
    "Tied maxima, empty arrays, and mixed widths are outside this condition."
)
NORMAL_PROMPT = '''from statistics import mode
from qiskit.primitives import BitArray
def most_common_result(bits: BitArray) -> str:
    """Return the unique most frequent bit string in a nonempty BitArray.

    All contained bit strings have the same width. Return a Python string
    consisting of `0` and `1`. Counts and input order may vary.
    """
'''
HARD_PROMPT = (
    "Implement most_common_result(bits). For a nonempty BitArray containing equal-width "
    "binary strings with a unique most frequent string, return that string as a Python "
    "string of `0` and `1`. Counts and input order may vary."
)
CHECK = """def check(candidate):
    from qiskit.primitives import BitArray

    cases = (
        {"1": 1},
        {"0": 2, "1": 7},
        {"1": 9, "0": 3},
        {"101": 3, "001": 50},
        {"001": 50, "101": 3},
        {"111": 4, "000": 2, "010": 20},
        {"010": 20, "111": 4, "000": 2},
        {"10": 2, "11": 4, "00": 7, "01": 1},
        {"10101010": 1, "00000000": 2, "11110000": 9},
    )
    for counts in cases:
        expected = max(counts, key=counts.get)
        observed = candidate(BitArray.from_counts(counts))
        assert type(observed) is str, "Expected Python str"
        assert observed == expected, "Incorrect most-common bit string"
"""


class MostCommonBitstringJudge:
    """Versioned public contract; the pinned task and verdicts stay historical."""

    def __init__(self, **kwargs):
        if kwargs.pop("protocol", 3) != 3:
            raise ValueError("Task 149 revision requires protected value protocol 3")
        if kwargs.pop("graph_transport", "snapshot-v1") != "snapshot-v1":
            raise ValueError("Task 149 value revision cannot use graph transport")
        self.inner = UpstreamJudge(protocol=3, **kwargs)

    def revise(self, task):
        if (
            task.public.family_id != "qhe/149"
            or task.public.task_id != "qiskitHumanEval/149"
            or task.public.entry_point != ENTRY
            or (task.public.suite == "normal")
            != (task.public.prompt_format == "function_completion")
        ):
            raise ValueError("Task 149 revision requires the matching family and prompt format")
        prompt = NORMAL_PROMPT if task.public.suite == "normal" else HARD_PROMPT
        return task.model_copy(
            update={
                "public": task.public.model_copy(update={"prompt": prompt}),
                "upstream_test": CHECK,
            }
        )

    def configuration(self, task):
        if task.digest != self.revise(task).digest:
            raise ValueError("Revise task 149 before generation and judgment")
        payload, inner = self.inner.configuration(task)
        return payload, {
            "track": RECIPE,
            "source": source_manifest(),
            "pinned_source_task_digest": PINNED_SOURCE_TASK_DIGESTS[task.public.suite],
            "task_digest": task.digest,
            "public_task_digest": task.public.digest,
            "public_contract": PUBLIC_CONTRACT,
            "domain": "Nonempty equal-width BitArray with a unique maximum count",
            "inner": inner,
            "release_eligible": False,
            "limitations": [
                "Nine authored count patterns are not an exhaustive input proof",
                "Ties, empty arrays, mixed widths, and stateful candidates are not qualified",
                "Value transport and candidate-side encoder integrity need protected controls",
                "Independent oracle and task-card reviews are missing",
            ],
        }

    def evaluate(self, task, completion):
        _, manifest = self.configuration(task)
        result = self.inner.evaluate(task, completion)
        return Judgment(
            result.outcome, identity(manifest), {"manifest": manifest, "inner": result.evidence}
        )

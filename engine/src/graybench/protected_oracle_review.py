"""Authored controls for development-only, cross-process value revisions.

These controls test the declared value semantics. They do not attest that the
candidate produced native Qiskit objects or used a particular algorithm.
"""

from pathlib import Path

from graybench.datasets import JudgeTask, load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.protected_semantic_judge import ProtectedSemanticJudge
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import ValueRunner


def protected_probes(source: JudgeTask) -> tuple[Probe, ...]:
    if source.public.task_id == "qiskitHumanEval/2":
        return (
            Probe(
                "analytic-phi-plus",
                "pass",
                "The Bell amplitudes are correct without a Qiskit implementation",
                "def bell_amplitudes():\n"
                "    from math import sqrt\n"
                "    a = 1 / sqrt(2)\n"
                "    return [[a,0],[0,0],[0,0],[a,0]]\n",
            ),
            Probe(
                "qiskit-phi-plus",
                "pass",
                "A circuit-derived independent construction gives the same value",
                "def bell_amplitudes():\n"
                "    from qiskit import QuantumCircuit\n"
                "    from qiskit.quantum_info import Statevector\n"
                "    qc = QuantumCircuit(2)\n"
                "    qc.h(0)\n"
                "    qc.cx(0, 1)\n"
                "    return [[float(z.real),float(z.imag)] for z in Statevector(qc).data]\n",
            ),
            Probe(
                "global-phase-phi-plus",
                "pass",
                "Global phase does not change the represented state",
                "def bell_amplitudes():\n"
                "    from math import sqrt\n"
                "    a = 1 / sqrt(2)\n"
                "    return [[0,a],[0,0],[0,0],[0,a]]\n",
            ),
            Probe(
                "product-zero",
                "fail",
                "The all-zero product state is not entangled Phi+",
                "def bell_amplitudes():\n    return [[1,0],[0,0],[0,0],[0,0]]\n",
            ),
            Probe(
                "psi-plus",
                "fail",
                "Psi+ has support on the wrong computational basis states",
                "def bell_amplitudes():\n"
                "    from math import sqrt\n"
                "    a = 1 / sqrt(2)\n"
                "    return [[0,0],[a,0],[a,0],[0,0]]\n",
            ),
            Probe(
                "relative-minus",
                "fail",
                "A relative minus phase gives Phi- rather than Phi+",
                "def bell_amplitudes():\n"
                "    from math import sqrt\n"
                "    a = 1 / sqrt(2)\n"
                "    return [[a,0],[0,0],[0,0],[-a,0]]\n",
            ),
        )
    if source.public.task_id == "qiskitHumanEval/20":
        return (
            Probe(
                "analytic-all-layouts",
                "pass",
                "The amplitudes depend on the requested ordered wire layout",
                "def ghz_amplitudes(layout):\n"
                "    from math import sqrt\n"
                "    result = [[0.0,0.0] for _ in range(128)]\n"
                "    result[0][0] = 1 / sqrt(2)\n"
                "    result[sum(1 << wire for wire in layout)][0] = 1 / sqrt(2)\n"
                "    return result\n",
            ),
            Probe(
                "qiskit-all-layouts",
                "pass",
                "A circuit-derived construction works for every ordered layout",
                "def ghz_amplitudes(layout):\n"
                "    from qiskit import QuantumCircuit\n"
                "    from qiskit.quantum_info import Statevector\n"
                "    qc = QuantumCircuit(7)\n"
                "    qc.h(layout[0])\n"
                "    qc.cx(layout[0], layout[1])\n"
                "    qc.cx(layout[0], layout[2])\n"
                "    return [[float(z.real),float(z.imag)] for z in Statevector(qc).data]\n",
            ),
            Probe(
                "global-phase-all-layouts",
                "pass",
                "Global phase is immaterial for every ordered layout",
                "def ghz_amplitudes(layout):\n"
                "    from math import sqrt\n"
                "    result = [[0.0,0.0] for _ in range(128)]\n"
                "    result[0][1] = 1 / sqrt(2)\n"
                "    result[sum(1 << wire for wire in layout)][1] = 1 / sqrt(2)\n"
                "    return result\n",
            ),
            Probe(
                "product-zero",
                "fail",
                "A product state lacks the requested GHZ coherence",
                "def ghz_amplitudes(layout):\n"
                "    return [[1.0,0.0]] + [[0.0,0.0] for _ in range(127)]\n",
            ),
            Probe(
                "fixed-layout",
                "fail",
                "The candidate ignores the requested layout",
                "def ghz_amplitudes(layout):\n"
                "    from math import sqrt\n"
                "    result = [[0.0,0.0] for _ in range(128)]\n"
                "    result[0][0] = result[84][0] = 1 / sqrt(2)\n"
                "    return result\n",
            ),
            Probe(
                "relative-minus",
                "fail",
                "A relative minus phase gives GHZ- rather than GHZ+",
                "def ghz_amplitudes(layout):\n"
                "    from math import sqrt\n"
                "    result = [[0.0,0.0] for _ in range(128)]\n"
                "    result[0][0] = 1 / sqrt(2)\n"
                "    result[sum(1 << wire for wire in layout)][0] = -1 / sqrt(2)\n"
                "    return result\n",
            ),
        )
    raise ValueError("No authored protected controls for this source task")


def run_protected_review(
    cache: Path,
    output: Path,
    *,
    suite: str,
    image: str,
    task_ids: tuple[str, ...] = ("qiskitHumanEval/2", "qiskitHumanEval/20"),
    docker: str = "docker",
    timeout: float = 120.0,
) -> dict:
    """Freeze judges and probes first, then record each control in an append-only log."""
    suites = ("normal", "hard") if suite == "both" else (suite,)
    if not suites or any(name not in {"normal", "hard"} for name in suites):
        raise ValueError("Unknown protected-control suite")
    if (
        not task_ids
        or len(set(task_ids)) != len(task_ids)
        or any(task_id not in {"qiskitHumanEval/2", "qiskitHumanEval/20"} for task_id in task_ids)
    ):
        raise ValueError("Unknown or duplicate protected-control task")
    runner = ValueRunner(image=image, docker=docker, timeout=timeout)
    judge = ProtectedSemanticJudge(runner)
    sources = tuple(
        task
        for name in suites
        for task in load_suite(name, cache)
        if task.public.task_id in task_ids
    )
    if len(sources) != len(suites) * len(task_ids):
        raise ValueError("Pinned source cache lacks a requested protected-control task")
    revisions = {
        f"{source.public.suite}/{source.public.task_id}": revised_value_task(source)
        for source in sources
    }
    declared = {key: judge.manifest(revision) for key, revision in revisions.items()}

    class BoundJudge:
        def evaluate(self, source: JudgeTask, completion: str):
            key = f"{source.public.suite}/{source.public.task_id}"
            return judge.evaluate(revisions[key], source, completion)

    run_review(
        sources,
        BoundJudge(),
        output,
        probes_for=protected_probes,
        declared_judges=declared,
    )
    return inspect_oracle_review(output, cache)

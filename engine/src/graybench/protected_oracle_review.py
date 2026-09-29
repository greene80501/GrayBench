"""Authored controls for development-only, cross-process value revisions.

These controls test the declared value semantics. They do not attest that the
candidate produced native Qiskit objects or used a particular algorithm.
"""

from pathlib import Path

from graybench.datasets import JudgeTask, load_suite
from graybench.oracle_review import Probe, inspect_oracle_review, run_review
from graybench.protected_semantic_judge import (
    TASK62_ORACLE,
    TASK62_ORACLE_V2,
    ProtectedSemanticJudge,
)
from graybench.protected_task_registry import revised_value_task
from graybench.protected_value_runner import ValueRunner


def _task62_analytic_completion(
    *,
    phase: bool = False,
    ignore_state: bool = False,
    ignore_basis: bool = False,
    reverse_order: bool = False,
    wrong_x_sign: bool = False,
) -> str:
    """Freeze readable, valid-output controls without using the trusted oracle."""
    return (
        "def bb84_sender_amplitudes(state, basis):\n"
        "    import math\n"
        f"    bits = [0] * len(state) if {ignore_state!r} else state\n"
        f"    axes = [0] * len(basis) if {ignore_basis!r} else basis\n"
        "    pairs = list(zip(bits, axes))\n"
        f"    if {reverse_order!r}: pairs.reverse()\n"
        "    vector = [1.0]\n"
        "    for bit, axis in pairs:\n"
        "        if axis == 0:\n"
        "            single = [0.0, 1.0] if bit else [1.0, 0.0]\n"
        "        else:\n"
        f"            sign = -1.0 if bit and not {wrong_x_sign!r} else 1.0\n"
        "            single = [1 / math.sqrt(2), sign / math.sqrt(2)]\n"
        "        vector = [amplitude * component for component in single for amplitude in vector]\n"
        f"    return [[0.0, float(amplitude)] for amplitude in vector] if {phase!r} "
        "else [[float(amplitude), 0.0] for amplitude in vector]\n"
    )


def _task62_omitted_input_mutant_completion() -> str:
    """Correct BB84 values except at one valid input omitted by v1."""
    return (
        "def bb84_sender_amplitudes(state, basis):\n"
        "    import math\n"
        "    if state == [1, 0, 0, 0] and basis == [0, 0, 0, 0]:\n"
        "        state = [0, 0, 0, 0]\n"
        "    vector = [1.0]\n"
        "    for bit, axis in zip(state, basis):\n"
        "        if axis == 0:\n"
        "            single = [0.0, 1.0] if bit else [1.0, 0.0]\n"
        "        else:\n"
        "            sign = -1.0 if bit else 1.0\n"
        "            single = [1 / math.sqrt(2), sign / math.sqrt(2)]\n"
        "        vector = [amplitude * component for component in single for amplitude in vector]\n"
        "    return [[float(amplitude), 0.0] for amplitude in vector]\n"
    )


def protected_probes(source: JudgeTask, *, oracle: str | None = None) -> tuple[Probe, ...]:
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
    if source.public.task_id == "qiskitHumanEval/62":
        if oracle not in (None, TASK62_ORACLE, TASK62_ORACLE_V2):
            raise ValueError("Unknown task-62 protected oracle for controls")
        probes = (
            Probe(
                "analytic-bb84",
                "pass",
                "Independent tensor product construction covers state and basis inputs",
                _task62_analytic_completion(),
            ),
            Probe(
                "qiskit-bb84",
                "pass",
                "Qiskit circuit-derived statevector realizes the same public value",
                "def bb84_sender_amplitudes(state, basis):\n"
                "    from qiskit import QuantumCircuit\n"
                "    from qiskit.quantum_info import Statevector\n"
                "    circuit = QuantumCircuit(len(state))\n"
                "    for wire, (bit, axis) in enumerate(zip(state, basis)):\n"
                "        if bit: circuit.x(wire)\n"
                "        if axis: circuit.h(wire)\n"
                "    return [[float(z.real), float(z.imag)] for z in Statevector(circuit).data]\n",
            ),
            Probe(
                "global-phase-bb84",
                "pass",
                "A common phase of i must leave the sender state equivalent",
                _task62_analytic_completion(phase=True),
            ),
            Probe(
                "fixed-zero-bb84",
                "fail",
                "A well-formed fixed all-zero state ignores both requested inputs",
                _task62_analytic_completion(ignore_state=True, ignore_basis=True),
            ),
            Probe(
                "ignored-state-bb84",
                "fail",
                "The answer depends on the requested sender bits",
                _task62_analytic_completion(ignore_state=True),
            ),
            Probe(
                "ignored-basis-bb84",
                "fail",
                "The answer depends on the requested preparation bases",
                _task62_analytic_completion(ignore_basis=True),
            ),
            Probe(
                "reversed-order-bb84",
                "fail",
                "Qubit order affects asymmetric sender states",
                _task62_analytic_completion(reverse_order=True),
            ),
            Probe(
                "wrong-x-sign-bb84",
                "fail",
                "An X-basis one is minus, not plus",
                _task62_analytic_completion(wrong_x_sign=True),
            ),
        )
        if oracle == TASK62_ORACLE_V2:
            return (
                *probes,
                Probe(
                    "omitted-input-bb84",
                    "fail",
                    "One valid width-4 input omitted by v1 receives a wrong state",
                    _task62_omitted_input_mutant_completion(),
                ),
            )
        return probes
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
        or any(
            task_id not in {"qiskitHumanEval/2", "qiskitHumanEval/20", "qiskitHumanEval/62"}
            for task_id in task_ids
        )
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

    def probes_for_source(source: JudgeTask) -> tuple[Probe, ...]:
        key = f"{source.public.suite}/{source.public.task_id}"
        return protected_probes(source, oracle=revisions[key].oracle)

    run_review(
        sources,
        BoundJudge(),
        output,
        probes_for=probes_for_source,
        declared_judges=declared,
    )
    return inspect_oracle_review(output, cache)

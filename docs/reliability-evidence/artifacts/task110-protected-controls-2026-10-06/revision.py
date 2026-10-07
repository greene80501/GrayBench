"""Development-only, source-bound protected graph revision of QHE task 110."""

import argparse
import hashlib
import json
from pathlib import Path

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask, load_suite
from graybench.identity import identity
from graybench.judge import Judgment
from graybench.oracle_review import Probe, run_review
from graybench.provenance import source_manifest
from graybench.upstream import UpstreamJudge

SOURCE_DIGESTS = {
    "normal": "da6ad9bb17b1f7437d7b709e9905b6e8e7fa82c282b76bd25466e89f3cc337d1",
    "hard": "7ff2acaded27c33c081fa11fd44fa7ec3b9413b77cc17e1c6eba28f2ee05dbe1",
}
TRACK = "qhe110-clifford-list-graph-v1"
REQUIREMENT = (
    "Given a Qiskit QuantumCircuit implementing a Clifford operation and an integer n "
    "from 0 through 10, return a Python list of exactly n Qiskit QuantumCircuit "
    "objects. Every returned circuit must have the input's qubit count and "
    "implement the same Clifford operation up to global phase. Circuit syntax "
    "may differ, and repeated equivalent circuits are allowed. Return the list "
    "directly. This contract checks the circuit results, not how they were made."
)
CHECK = """def check(candidate):
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Clifford
    one = QuantumCircuit(1)
    one.h(0)
    two = QuantumCircuit(2)
    two.h(0)
    two.cx(0, 1)
    three = QuantumCircuit(3)
    three.s(1)
    three.cx(1, 2)
    three.h(0)
    five = QuantumCircuit(5)
    five.h(0)
    five.s(3)
    five.cx(0, 4)
    for source, n in ((one, 0), (one, 1), (two, 3), (three, 2), (five, 10)):
        expected = Clifford(source)
        items = candidate(source, n)
        assert isinstance(items, list), 'Expected a Python list'
        assert len(items) == n, 'Incorrect number of circuits'
        for item in items:
            assert isinstance(item, QuantumCircuit), 'Expected a QuantumCircuit'
            assert item.num_qubits == source.num_qubits, 'Incorrect qubit count'
            try:
                actual = Clifford(item)
            except Exception as exc:
                raise AssertionError('Returned circuit is not Clifford') from exc
            assert actual == expected, 'Incorrect Clifford operation'
"""


def revised_task(source: JudgeTask) -> JudgeTask:
    if (
        source.public.task_id != "qiskitHumanEval/110"
        or source.public.entry_point != "equivalent_clifford_circuit"
        or source.digest != SOURCE_DIGESTS.get(source.public.suite)
    ):
        raise ValueError("Expected the exact pinned QHE task-110 source")
    if source.public.suite == "normal":
        prompt = (
            "from qiskit import QuantumCircuit\n"
            "def equivalent_clifford_circuit(circuit: QuantumCircuit, n: int) -> list:\n"
            f'    """{REQUIREMENT}"""\n'
        )
    else:
        prompt = REQUIREMENT + " Implement equivalent_clifford_circuit(circuit, n) in Python."
    public = PublicTask(
        suite=source.public.suite,
        task_id=source.public.task_id,
        family_id=source.public.family_id,
        prompt=prompt,
        entry_point=source.public.entry_point,
        prompt_format=source.public.prompt_format,
    )
    return JudgeTask(
        public=public,
        canonical_solution=source.canonical_solution,
        upstream_test=CHECK,
        upstream_difficulty=source.upstream_difficulty,
    )


class Task110GraphJudge:
    """Graph-isolated test of the adapted deterministic Clifford-list contract."""

    def __init__(self, *, image: str, docker: str = "docker"):
        self.inner = UpstreamJudge(
            image=image, docker=docker, protocol=4, graph_transport="snapshot-v1"
        )

    def configuration(self, source: JudgeTask) -> tuple[dict, dict]:
        task = revised_task(source)
        payload, inner = self.inner.configuration(task)
        manifest = {
            "track": TRACK,
            "release_eligible": False,
            "source": source_manifest(),
            "source_task_digest": source.digest,
            "public_contract_digest": task.public.digest,
            "revised_task_digest": task.digest,
            "revision_file_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "inner": inner,
        }
        return payload, manifest

    def evaluate(self, source: JudgeTask, completion: str) -> Judgment:
        _, manifest = self.configuration(source)
        result = self.inner.evaluate(revised_task(source), completion)
        return Judgment(
            result.outcome,
            identity(manifest),
            {"manifest": manifest, "inner": result.evidence},
        )


def _completion(source: JudgeTask, body: str) -> str:
    indented = "".join(f"    {line}\n" for line in body.splitlines())
    if source.public.suite == "normal":
        return "\n" + indented
    return "def equivalent_clifford_circuit(circuit, n):\n" + indented


def probes(source: JudgeTask) -> tuple[Probe, ...]:
    revised_task(source)
    controls = (
        (
            "copies",
            "pass",
            "Independent circuit copies satisfy the declared deterministic contract",
            "return [circuit.copy() for _ in range(n)]",
        ),
        (
            "global-phase",
            "pass",
            "A changed global phase preserves the Clifford operation",
            "import math\n"
            "out = []\n"
            "for _ in range(n):\n"
            "    item = circuit.copy()\n"
            "    item.global_phase += math.pi / 2\n"
            "    out.append(item)\n"
            "return out",
        ),
        (
            "canceling-pair",
            "pass",
            "Two extra X gates change syntax but cancel semantically",
            "out = []\n"
            "for _ in range(n):\n"
            "    item = circuit.copy()\n"
            "    item.x(0)\n"
            "    item.x(0)\n"
            "    out.append(item)\n"
            "return out",
        ),
        ("empty", "fail", "Native false pass omits all requested outputs", "return []"),
        (
            "short-list",
            "fail",
            "One output is missing whenever n is positive",
            "return [circuit.copy() for _ in range(max(0, n - 1))]",
        ),
        (
            "wrong-width",
            "fail",
            "Returned circuits have an extra qubit",
            "from qiskit import QuantumCircuit\n"
            "return [QuantumCircuit(circuit.num_qubits + 1) for _ in range(n)]",
        ),
        (
            "wrong-action",
            "fail",
            "Appending X changes the Clifford action",
            "out = []\n"
            "for _ in range(n):\n"
            "    item = circuit.copy()\n"
            "    item.x(0)\n"
            "    out.append(item)\n"
            "return out",
        ),
        (
            "non-clifford",
            "fail",
            "Appending T leaves the Clifford group",
            "out = []\n"
            "for _ in range(n):\n"
            "    item = circuit.copy()\n"
            "    item.t(0)\n"
            "    out.append(item)\n"
            "return out",
        ),
        (
            "wrong-type",
            "fail",
            "Non-circuit values cannot satisfy the public return contract",
            "return [None for _ in range(n)]",
        ),
    )
    return tuple(
        Probe(name, expected, rationale, _completion(source, body))
        for name, expected, rationale, body in controls
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = tuple(load_suite(suite, args.cache)[110] for suite in ("normal", "hard"))
    judge = Task110GraphJudge(image=args.image)
    declared = {
        f"{source.public.suite}/{source.public.task_id}": judge.configuration(source)[1]
        for source in sources
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = run_review(
        sources,
        judge,
        args.output,
        probes_for=probes,
        declared_judges=declared,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

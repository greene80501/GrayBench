"""Live judge-state race classification; controlled faults, not model scoring."""

import json
import sys
from pathlib import Path

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.identity import identity
from graybench.reference_scan import run_evidence_cases
from graybench.upstream import UpstreamJudge

code = "def answer(value): return value"
cases = []
for transport in ("snapshot-v1", "delta-v1"):
    for change in ("99", "object()"):
        test = """from graybench.graph_wire import GraphArena
original_commit = GraphArena.commit
held = [1]
def changed_commit(self, prepared):
    if self.side == 'judge': held.append(MUTATION)
    return original_commit(self, prepared)
GraphArena.commit = changed_commit
def check(candidate):
    try: candidate(held)
    except BaseException: pass
    assert True
""".replace("MUTATION", change)
        key = transport + "/" + ("value" if change == "99" else "unsupported")
        task = JudgeTask(
            public=PublicTask(suite="hard", task_id=key, family_id=key, prompt="Implement answer.",
                              entry_point="answer", prompt_format="standalone_function"),
            canonical_solution=code, upstream_test=test, upstream_difficulty="fixture",
        )
        cases.append((key, identity({"task": task.digest, "code": code}), (task, transport)))


def evaluate(item):
    task, transport = item
    judge = UpstreamJudge(
        image="sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd",
        docker="C:/Program Files/Docker/Docker/resources/bin/docker.exe",
        protocol=4, graph_transport=transport,
    )
    return judge.evaluate(task, code)


print(json.dumps(run_evidence_cases(cases, evaluate, Path(sys.argv[1]), purpose=__doc__,
                                    selection={"protocol": 4, "faults": 4})))

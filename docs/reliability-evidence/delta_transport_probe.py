"""Compare protected transport under the same cumulative one-MiB budget."""

import json
import sys
from pathlib import Path

from graybench.contracts import PublicTask
from graybench.datasets import JudgeTask
from graybench.identity import identity
from graybench.reference_scan import run_evidence_cases
from graybench.upstream import UpstreamJudge

code = """held = None
def answer(value=None):
    global held
    if value is not None:
        held = value
        return held
    held[0] += 1
    return held[0]
"""
test = """def check(candidate):
    held = [0, ['x' * 20000]]
    assert candidate(held) is held
    for i in range(1, 61):
        assert candidate() == i
        assert held[0] == i
"""
task = JudgeTask(
    public=PublicTask(suite="hard", task_id="transport/retained-state", family_id="transport/retained-state",
                      prompt="Implement answer.", entry_point="answer", prompt_format="standalone_function"),
    canonical_solution=code, upstream_test=test, upstream_difficulty="fixture",
)
judge = UpstreamJudge(
    image="sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd",
    docker="C:/Program Files/Docker/Docker/resources/bin/docker.exe", protocol=4,
    graph_transport=sys.argv[1],
)
print(json.dumps(run_evidence_cases(
    [("retained-state/one-mib", identity({"task": task.digest, "code": code}), (task, code))],
    lambda item: judge.evaluate(*item), Path(sys.argv[2]), purpose=__doc__,
    selection={"protocol": 4, "output_limit": 1048576, "calls": 61},
)))

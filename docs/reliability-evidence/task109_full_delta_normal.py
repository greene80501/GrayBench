from pathlib import Path
import json
from graybench.datasets import load_suite
from graybench.reference_scan import run_reference_scan
from graybench.upstream import UpstreamJudge

tasks = [t for t in load_suite('normal', Path('../../GrayBench/data/datasets')) if int(t.public.task_id.split('/')[-1]) == 109]
assert len(tasks) == 1
judge = UpstreamJudge(image='sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd', docker='C:/Program Files/Docker/Docker/resources/bin/docker.exe', protocol=4, graph_transport='delta-v1', output_limit=16777216, graph_state_limit=16777216, timeout=3600, candidate_timeout=3600)
print(json.dumps(run_reference_scan(tasks, judge, Path('../../../outputs/GrayBench-v4-task109-full-delta-normal-0379d13.jsonl'), selection={'families':[109], 'suites':['normal'], 'bridge_protocol':4, 'graph_transport':'delta-v1', 'output_limit':16777216, 'graph_state_limit':16777216, 'judge_timeout':3600, 'candidate_timeout':3600, 'purpose':'unmodified 1000-call reference workload; explicit diagnostic ceilings, not production calibration or model scoring'})), flush=True)

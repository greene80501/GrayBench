from pathlib import Path
import json,sys
from graybench.datasets import load_suite
from graybench.reference_scan import run_reference_scan
from graybench.upstream import UpstreamJudge
families={90,91,112,119,120,125}
tasks=[t for suite in ('normal','hard') for t in load_suite(suite,Path('../../GrayBench/data/datasets')) if int(t.public.family_id.split('/')[-1]) in families]
assert len(tasks)==12
judge=UpstreamJudge(image='sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd',docker='C:/Program Files/Docker/Docker/resources/bin/docker.exe',protocol=4)
print(json.dumps(run_reference_scan(tasks,judge,Path(sys.argv[1]),selection={'families':sorted(families),'suites':['normal','hard'],'bridge_protocol':4,'purpose':'converter metadata interface calibration; not model scoring'})),flush=True)

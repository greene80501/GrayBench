from pathlib import Path
import json,sys
from graybench.datasets import load_suite
from graybench.reference_scan import run_reference_scan
from graybench.upstream import UpstreamJudge
tasks=[t for suite in ('normal','hard') for t in load_suite(suite,Path('../../GrayBench/data/datasets')) if t.public.family_id in {'qhe/78','qhe/101','qhe/145'}]
assert len(tasks)==6
judge=UpstreamJudge(image='sha256:2fc74bd3dd29a28154c566e21610072e24cda279c3d03f3ab8cd27f33c9b27bd',docker='C:/Program Files/Docker/Docker/resources/bin/docker.exe',protocol=4)
print(json.dumps(run_reference_scan(tasks,judge,Path(sys.argv[1]),selection={'families':[78,101,145],'suites':['normal','hard'],'bridge_protocol':4,'purpose':'fixed circuit subclass interface calibration; not model scoring'})),flush=True)

from pathlib import Path
import json
from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan
paths=[Path('../../../outputs/GrayBench-v4-diagonal-reference-'+side+'.jsonl') for side in ('before','after')]
verified=[inspect_reference_scan(path) for path in paths]
assert all(v['complete'] and v['planned']==2 for v in verified)
events=[[json.loads(line)['event'] for line in path.read_text(encoding='utf-8').splitlines()] for path in paths]
headers=[rows[0] for rows in events]
assert headers[0]['tasks']==headers[1]['tasks'] and headers[0]['selection']==headers[1]['selection']
assert headers[1]['source']==source_manifest()
changed=[name for name in headers[0]['source']['files'] if headers[0]['source']['files'][name]!=headers[1]['source']['files'].get(name)]
assert changed==['graph_instruction.py'],changed
results=[{e['task_key']:e for e in rows if e['kind']=='result'} for rows in events]
for key,before in results[0].items():
    after=results[1][key]
    assert before['outcome']=='unsupported' and after['outcome']=='pass'
    for field in ('completion_sha256','extracted_code_sha256','public_task_digest'):
        assert before['evidence'][field]==after['evidence'][field]
    for result in (before,after): assert identity(result['evidence']['manifest'])==result['judge_digest']
print(json.dumps({'verified':verified,'same_task_selection_completion':True,'changed_runtime_files':changed,'after_source_matches':True}))

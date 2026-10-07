from pathlib import Path
import json
from graybench.identity import identity
from graybench.provenance import source_manifest
from graybench.reference_scan import inspect_reference_scan

paths = [Path('../../../outputs/GrayBench-v4-circuit-subclasses-' + name + '.jsonl') for name in ('before', 'after', 'after-final')]
verified = [inspect_reference_scan(path) for path in paths]
assert all(row['complete'] and row['planned'] == 6 for row in verified)
events = [[json.loads(line)['event'] for line in path.read_text(encoding='utf-8').splitlines()] for path in paths]
headers = [rows[0] for rows in events]
assert headers[2]['source'] == source_manifest()
for header in headers[1:]:
    assert header['tasks'] == headers[0]['tasks']
    assert header['selection'] == headers[0]['selection']
changed = [name for name in headers[0]['source']['files'] if headers[0]['source']['files'][name] != headers[2]['source']['files'].get(name)]
assert sorted(changed) == ['graph_instruction.py', 'graph_quantum_circuit.py']
results = [{e['task_key']:e for e in rows if e['kind'] == 'result'} for rows in events]
for key, before in results[0].items():
    assert before['outcome'] == 'unsupported'
    for group in results[1:]:
        after = group[key]
        assert after['outcome'] == 'pass'
        for field in ('completion_sha256', 'extracted_code_sha256', 'public_task_digest'):
            assert before['evidence'][field] == after['evidence'][field]
    for group in results:
        result = group[key]
        assert identity(result['evidence']['manifest']) == result['judge_digest']
summary = {'verified':verified, 'same_task_selection_completion':True, 'changed_runtime_files':changed, 'final_source_matches':True, 'pre_final_difference':'Ruff import ordering in graph_quantum_circuit.py; intermediate evidence preserved'}
target = Path('../../../outputs/GrayBench-v4-circuit-subclasses-summary.json')
with target.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(summary, stream, indent=2)
    stream.write('\n')
print(json.dumps(summary))

from pathlib import Path
import copy,json,tempfile
from graybench.identity import identity,canonical
from audit_delta_transcript import audit
path=Path('../docs/reliability-evidence/GrayBench-v4-transport-delta.jsonl')
original=[json.loads(line)['event'] for line in path.read_text().splitlines()]
verified=[]
for mutation in ('result_digest','base','sequence','duplicate_node','transcript_hash','state_limit'):
    events=copy.deepcopy(original)
    result=next(e for e in events if e['kind']=='result')
    evidence=result['evidence']
    row=evidence['transcript'][-1]
    frame=row['response_data']['response']['graph']
    if mutation=='result_digest': frame['digest']='0'*64
    elif mutation=='base': frame['base']='0'*64
    elif mutation=='sequence': frame['sequence']+=1
    elif mutation=='duplicate_node': frame['nodes'].append(copy.deepcopy(frame['nodes'][0]))
    elif mutation=='state_limit':
        evidence['manifest']['graph_transport']['state_bytes']=1024
        result['judge_digest']=identity(evidence['manifest'])
    if mutation=='transcript_hash': row['response']='0'*64
    else: row['response']=identity(row['response_data'])
    with tempfile.TemporaryDirectory() as directory:
        target=Path(directory)/'tampered.jsonl'
        previous='0'*64
        with target.open('wb') as stream:
            for sequence,event in enumerate(events,1):
                payload={'sequence':sequence,'previous':previous,'event':event}
                digest=identity(payload)
                stream.write(canonical({**payload,'digest':digest})+b'\n')
                previous=digest
        try: audit(target)
        except AssertionError: verified.append(mutation)
        else: raise AssertionError('Mutation escaped: '+mutation)
assert len(verified)==6
print(json.dumps({'rejected_with_valid_outer_event_chains':verified}))

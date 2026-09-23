"""Data-only audit of stored delta transcripts; never executes graph objects."""
from pathlib import Path
import hashlib
import json
import sys
from graybench.identity import identity
from graybench.reference_scan import inspect_reference_scan

def wire(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',', ':'), sort_keys=True).encode()

def audit(path):
    summary = inspect_reference_scan(path)
    if not summary['complete']:
        return {'evidence':summary, 'transcripts':'pending; no completed scan claim'}
    events = [json.loads(line)['event'] for line in path.read_text(encoding='utf-8').splitlines()]
    results=[]
    for event in events:
        if event['kind']!='result': continue
        evidence=event['evidence']
        manifest=evidence['manifest']
        assert identity(manifest)==event['judge_digest']
        assert manifest['graph_transport']['mode']=='delta-v1'
        state_cap=manifest['graph_transport']['state_bytes']
        frame_cap=manifest['graph_transport']['wire_bytes']
        session=evidence['graph_session']
        records={}
        digest=None
        frames=[]
        calls=evidence['transcript']
        for sequence, row in enumerate(calls, 1):
            call,response=row['call_data'],row['response_data']
            assert identity(call)==row['call'] and identity(response)==row['response']
            assert call['kind']=='call' and call['sequence']==response['sequence']==sequence
            pair=[('judge',call['graph'])]
            returned=response.get('response',{})
            if 'graph' in returned:
                assert response['outcome']=='returned'
                assert returned['protocol']==4 and returned['sequence']==sequence
                pair.append(('candidate',returned['graph']))
            else:
                assert sequence==len(calls), 'A failed graph response must terminate the transcript'
            for side,frame in pair:
                assert frame['format']=='call_graph_delta_v1'
                assert frame['session']==session and frame['sequence']==sequence and frame['side']==side
                assert frame['base']==digest
                assert len(wire(frame))<=frame_cap
                changes={node['id']:node for node in frame['nodes']}
                assert len(changes)==len(frame['nodes'])
                records.update(changes)
                assert len(records)<=manifest['graph_limits']['nodes']
                snapshot={'format':'call_graph_anchors_v1','session':session,'sequence':sequence,'anchors':frame['anchors'],'roots':frame['roots'],'nodes':[records[key] for key in sorted(records)]}
                raw=wire(snapshot)
                assert len(raw)<=state_cap
                digest=hashlib.sha256(raw).hexdigest()
                assert digest==frame['digest']
                frames.append({'sequence':sequence,'side':side,'nodes':len(records),'changed_nodes':len(changes),'state_bytes':len(raw),'frame_bytes':len(wire(frame))})
        if event['outcome']=='pass':
            assert all(row['response_data'].get('response',{}).get('graph') for row in calls)
        results.append({'task':event['task_key'],'outcome':event['outcome'],'recorded_calls':len(calls),'frames':len(frames),'graph_frame_bytes':sum(row['frame_bytes'] for row in frames),'first_frame':frames[0] if frames else None,'last_frame':frames[-1] if frames else None,'candidate_active_seconds':evidence.get('candidate_active_seconds'),'judge_wait_seconds':evidence.get('judge_wait_seconds'),'wall_seconds':evidence.get('wall_seconds'),'detail':evidence.get('detail')})
    return {'evidence':summary,'results':results,'verification':'event and transcript hashes, manifest digest, bidirectional delta bases/result hashes, session/sequence, and declared node/state/frame bounds; data only, not SDK semantic re-execution'}

if __name__=='__main__':
    result=audit(Path(sys.argv[1]))
    if len(sys.argv)>2:
        with Path(sys.argv[2]).open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(result,stream,indent=2)
            stream.write('\n')
    print(json.dumps(result))

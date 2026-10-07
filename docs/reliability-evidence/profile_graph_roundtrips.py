import hashlib,json,platform,time
from pathlib import Path
import qiskit
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from graybench.graph_anchors import PublicAnchorRegistry
from graybench.graph_wire import GraphArena,GraphLimits,wire_bytes
from graybench.provenance import source_manifest
source=source_manifest()
registry=PublicAnchorRegistry.capture()
judge,candidate=(GraphArena(side=s,session='profile-repeated-circuits',limits=GraphLimits(message_bytes=16777216),anchors=registry) for s in ('judge','candidate'))
known={};rows=[];total_bytes=0

def measure(fn):
    started=time.perf_counter();value=fn();return value,time.perf_counter()-started

def describe(wire):
    global total_bytes,known
    size=len(wire_bytes(wire));total_bytes+=size
    encoded={r['id']:wire_bytes(r) for r in wire['nodes']}
    changed=[value for key,value in encoded.items() if known.get(key)!=value]
    known=encoded
    return {'nodes':len(encoded),'graph_bytes':size,'changed_records':len(changed),'changed_record_bytes':sum(map(len,changed))}

start=time.perf_counter()
for sequence in range(1,101):
    outgoing,t1=measure(lambda:judge.snapshot({'args':(),'kwargs':{}},sequence=sequence))
    forward=describe(outgoing)
    prepared,t2=measure(lambda:candidate.prepare(outgoing,sequence=sequence))
    args,t3=measure(lambda:candidate.commit(prepared))
    qc=QuantumCircuit(1);qc.h(0);qc.rz(Parameter('th'),0)
    response,t4=measure(lambda:candidate.snapshot({**args,'result':qc,'exception_args':None},sequence=sequence))
    backward=describe(response)
    prepared,t5=measure(lambda:judge.prepare(response,sequence=sequence))
    result,t6=measure(lambda:judge.commit(prepared))
    result['result'].assign_parameters([0.5],inplace=True)
    rows.append({'call':sequence,'forward':forward,'backward':backward,'seconds':{'judge_snapshot':t1,'candidate_prepare':t2,'candidate_commit':t3,'candidate_snapshot':t4,'judge_prepare':t5,'judge_commit':t6}})
    if sequence in (1,25,50,100):print(json.dumps({'call':sequence,'elapsed':time.perf_counter()-start,'bytes':total_bytes,'last':rows[-1]}),flush=True)
assert source_manifest()==source
result={'purpose':'local repeated-call graph profiling; not model scoring or protected timing','source':source,'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'python':platform.python_version(),'qiskit':qiskit.__version__,'message_limit':16777216,'calls':100,'elapsed_seconds':time.perf_counter()-start,'total_graph_bytes':total_bytes,'rows':rows,'limitations':['Local arenas share a process; no Docker, pipe or JSON-envelope costs.','changed_record_bytes is a hypothetical diff estimate, not a validated protocol.','No retained objects are discarded.']}
with Path('../../../outputs/GrayBench-native-graph-profile-46b7487.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
